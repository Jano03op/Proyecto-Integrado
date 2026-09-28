from datetime import date, datetime

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponseNotAllowed
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone

from cuentas.decorators import requiere_login
from cuentas.models import StaffProfile
from organizacion.models import Delegation
from .models import Commitment, CommitmentEvent

# Verificador y consulta son roles de solo lectura: no registran compromisos.
ROLES_SOLO_LECTURA = ['verificador', 'consulta']


def _get_user_role(request):
    if request.session.get('rol'):
        return request.session.get('rol')
    if getattr(request.user, "is_authenticated", False):
        if request.user.is_superuser or request.user.is_staff:
            return 'administrador'
        profile = getattr(request.user, 'staff_profile', None)
        if profile and profile.legacy_role:
            return profile.legacy_role.lower()
    return None


@requiere_login
def tablero_agenda(request):
    territorio = request.GET.get('territorio', '').strip()
    responsable = request.GET.get('responsable', '').strip()

    qs = Commitment.objects.select_related('delegation', 'owner').prefetch_related('events').all()
    if territorio:
        qs = qs.filter(Q(territory_label__iexact=territorio) | Q(delegation__name__iexact=territorio))
    if responsable:
        qs = qs.filter(owner__display_name__icontains=responsable)

    compromisos = list(qs)

    territorios_disponibles = list(
        Delegation.objects.values_list('name', flat=True).order_by('name')
    )
    if not territorios_disponibles:
        territorios_disponibles = sorted({c.territorio for c in compromisos if c.territorio})

    columnas = {estado: [] for estado in Commitment.Status.values}
    for c in compromisos:
        if c.status in columnas:
            columnas[c.status].append(c)

    contexto = {
        'columnas': columnas,
        'total_compromisos': len(compromisos),
        'territorio_filtro': territorio,
        'responsable_filtro': responsable,
        'territorios_disponibles': territorios_disponibles,
    }
    return render(request, 'agenda/tablero.html', contexto)


@requiere_login
def accion_pendiente(request, accion, id):
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])
    if accion not in ('editar', 'eliminar'):
        raise Http404
    return render(request, 'organizacion/accion_pendiente.html', {
        'accion': accion, 'recurso': 'compromiso', 'volver': 'tablero_agenda',
    })


@requiere_login
def crear_compromiso(request):
    user_rol = _get_user_role(request)
    if user_rol in ROLES_SOLO_LECTURA:
        messages.error(request, 'Tu rol no tiene permiso para registrar compromisos.')
        return redirect('tablero_agenda')

    if request.method == 'POST':
        origen = request.POST.get('origen', 'Solicitud ciudadana')
        solicitante = request.POST.get('solicitante', '').strip()
        territorio = request.POST.get('territorio', '').strip()
        responsable = request.POST.get('responsable', '').strip()
        area_apoyo = request.POST.get('area_apoyo', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        fecha_compromiso = request.POST.get('fecha_compromiso', '').strip()

        campos_obligatorios = [solicitante, territorio, responsable, fecha_compromiso, descripcion]
        if not all(campos_obligatorios):
            messages.error(request, 'Debe completar solicitante, territorio, responsable, fecha y descripción.')
            return render(request, 'agenda/crear_compromiso.html', {'valores': request.POST})

        try:
            due_date = datetime.strptime(fecha_compromiso, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, 'Fecha comprometida inválida. Use formato AAAA-MM-DD.')
            return render(request, 'agenda/crear_compromiso.html', {'valores': request.POST})

        # Resolve or create Delegation
        delegation = Delegation.objects.filter(name__iexact=territorio).first()
        if not delegation:
            delegation = Delegation.objects.create(name=territorio)

        # Resolve or create StaffProfile
        owner = StaffProfile.objects.filter(display_name__iexact=responsable).first()
        if not owner:
            owner = StaffProfile.objects.create(display_name=responsable, delegation=delegation)

        actor = request.user if getattr(request.user, "is_authenticated", False) else None
        if not actor:
            autor_nombre = request.session.get('persona_actual', '')
            if autor_nombre:
                staff_actor = StaffProfile.objects.filter(display_name__iexact=autor_nombre).select_related('user').first()
                if staff_actor and staff_actor.user:
                    actor = staff_actor.user

        commitment = Commitment(
            delegation=delegation,
            owner=owner,
            origin=origen,
            requester=solicitante,
            territory_label=territorio,
            support_area=area_apoyo,
            description=descripcion,
            due_on=due_date,
            status=Commitment.Status.INGRESADO,
            registered_on=date.today(),
        )
        if actor:
            commitment._current_actor = actor
            commitment._current_occurred_at = timezone.now()
        commitment.save()

        messages.success(request, f'Compromiso #{commitment.id} registrado correctamente en estado "Ingresado".')
        return redirect('tablero_agenda')

    valores_iniciales = {
        'responsable': request.session.get('persona_actual', ''),
    }
    return render(request, 'agenda/crear_compromiso.html', {'valores': valores_iniciales})


@requiere_login
def detalle_compromiso(request, id):
    try:
        compromiso = Commitment.objects.select_related('delegation', 'owner').prefetch_related('events').get(pk=id)
    except Commitment.DoesNotExist:
        messages.error(request, 'El compromiso solicitado no existe.')
        return redirect('tablero_agenda')

    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado', '').strip()
        observacion = request.POST.get('observacion', '').strip()

        actor = request.user if getattr(request.user, "is_authenticated", False) else None
        if not actor:
            autor_nombre = request.POST.get('autor', '').strip() or request.session.get('persona_actual', '')
            if autor_nombre:
                staff = StaffProfile.objects.filter(display_name__iexact=autor_nombre).select_related('user').first()
                if staff and staff.user:
                    actor = staff.user

        try:
            status_order = list(Commitment.Status.values)
            old_idx = status_order.index(compromiso.status)
            new_idx = status_order.index(nuevo_estado)
            allow_backward = False
            if new_idx < old_idx:
                user_role = _get_user_role(request)
                if user_role in ['administrador', 'coordinador', 'delegado']:
                    allow_backward = True
                elif actor and compromiso.can_reopen_or_retrocede(actor):
                    allow_backward = True

            compromiso.transition_to(
                next_status=nuevo_estado,
                actor=actor,
                note=observacion,
                allow_backward=allow_backward,
            )
            messages.success(request, f'El compromiso {id} ahora está en estado "{nuevo_estado}".')
        except ValidationError as e:
            error_msg = "; ".join(e.messages) if hasattr(e, "messages") else str(e)
            messages.error(request, f'No se pudo actualizar el estado: {error_msg}')
        except Exception as e:
            messages.error(request, f'Error al actualizar el estado: {e}')

        return redirect('detalle_compromiso', id=id)

    contexto = {
        'compromiso': compromiso,
        'estados': Commitment.Status.values,
    }
    return render(request, 'agenda/detalle_compromiso.html', contexto)
