from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from cuentas.decorators import requiere_login
from .forms import DelegacionForm
from .models import Delegation

PER_PAGE = 5

# Roles que pueden crear/editar/activar-desactivar delegaciones. El resto
# (funcionario, verificador, consulta) solo puede consultar el listado.
ROLES_GESTION = ['administrador', 'coordinador', 'delegado']


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


def _sin_permiso(request):
    messages.error(request, 'Tu rol no tiene permiso para modificar delegaciones.')
    return redirect('organizacion:delegaciones_list')


@requiere_login
def delegaciones_list(request):
    """Listado de delegaciones: búsqueda por nombre/ámbito + filtro de estado + paginación."""
    search = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', 'Todas')

    qs = Delegation.objects.annotate(n_funcionarios=Count('staff')).order_by('name')
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(scope__icontains=search))
    if estado == 'Activa':
        qs = qs.filter(status=Delegation.Status.ACTIVE)
    elif estado == 'Inactiva':
        qs = qs.filter(status=Delegation.Status.INACTIVE)

    paginator = Paginator(qs, PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))

    contexto = {
        'page_obj': page_obj,
        'search': search,
        'estado': estado,
        'total': qs.count(),
    }
    return render(request, 'organizacion/delegacion_list.html', contexto)


@requiere_login
def delegacion_create(request):
    if _get_user_role(request) not in ROLES_GESTION:
        return _sin_permiso(request)
    if request.method == 'POST':
        form = DelegacionForm(request.POST)
        if form.is_valid():
            estado_val = form.cleaned_data.get('estado')
            status_val = Delegation.Status.INACTIVE if estado_val == 'Inactiva' else Delegation.Status.ACTIVE
            Delegation.objects.create(
                name=form.cleaned_data['nombre'],
                scope=form.cleaned_data.get('ambito', ''),
                status=status_val,
            )
            messages.success(request, 'Delegación creada correctamente.')
            return redirect('organizacion:delegaciones_list')
    else:
        form = DelegacionForm()
    return render(request, 'organizacion/delegacion_form.html', {'form': form, 'editing': False})


@requiere_login
def delegacion_edit(request, pk):
    if _get_user_role(request) not in ROLES_GESTION:
        return _sin_permiso(request)
    try:
        delegacion = Delegation.objects.get(pk=pk)
    except Delegation.DoesNotExist:
        messages.error(request, 'La delegación solicitada no existe.')
        return redirect('organizacion:delegaciones_list')

    if request.method == 'POST':
        form = DelegacionForm(request.POST, excluir_id=pk)
        if form.is_valid():
            delegacion.name = form.cleaned_data['nombre']
            delegacion.scope = form.cleaned_data.get('ambito', '')
            estado_val = form.cleaned_data.get('estado')
            if estado_val:
                delegacion.status = Delegation.Status.INACTIVE if estado_val == 'Inactiva' else Delegation.Status.ACTIVE
            delegacion.save()
            messages.success(request, 'Cambios guardados correctamente.')
            return redirect('organizacion:delegaciones_list')
    else:
        form = DelegacionForm(
            initial={
                'nombre': delegacion.name,
                'ambito': delegacion.scope,
                'estado': 'Activa' if delegacion.status == Delegation.Status.ACTIVE else 'Inactiva',
            },
            excluir_id=pk,
        )
    return render(request, 'organizacion/delegacion_form.html', {
        'form': form, 'editing': True, 'delegacion': delegacion,
    })


@requiere_login
def delegacion_detail(request, pk):
    try:
        delegacion = Delegation.objects.annotate(n_funcionarios=Count('staff')).get(pk=pk)
    except Delegation.DoesNotExist:
        messages.error(request, 'La delegación solicitada no existe.')
        return redirect('organizacion:delegaciones_list')
    funcionarios = delegacion.staff.all().select_related('position', 'user')
    return render(request, 'organizacion/delegacion_detail.html', {
        'delegacion': delegacion,
        'funcionarios': funcionarios,
    })


@requiere_login
@require_POST
def delegacion_toggle_estado(request, pk):
    """Activa/desactiva una delegación. No elimina historial ni funcionarios asociados."""
    if _get_user_role(request) not in ROLES_GESTION:
        return _sin_permiso(request)
    try:
        delegacion = Delegation.objects.get(pk=pk)
    except Delegation.DoesNotExist:
        messages.error(request, 'La delegación solicitada no existe.')
        return redirect('organizacion:delegaciones_list')

    if delegacion.status == Delegation.Status.ACTIVE:
        delegacion.status = Delegation.Status.INACTIVE
        verbo = 'desactivada'
    else:
        delegacion.status = Delegation.Status.ACTIVE
        verbo = 'activada'
    delegacion.save()

    messages.success(request, f'Delegación "{delegacion.name}" {verbo}.')

    siguiente = request.POST.get('next')
    if siguiente:
        return redirect(siguiente)
    return redirect('organizacion:delegaciones_list')
