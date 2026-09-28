from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login, logout as auth_logout
from django.db.models import Q
from django.shortcuts import redirect, render

from agenda.models import Commitment
from .decorators import requiere_login
from .forms import BuscarUsuarioForm, LoginForm, NuevaPasswordForm, RegistroForm

REDIRECT_TRAS_LOGIN = 'cuentas:home'
SESSION_KEY_RECUPERAR = 'recuperar_usuario'


def _abrir_sesion(request, persona):
    """Guarda en la sesión quién inició sesión y su rol. De aquí lo leen
    tanto el navbar compartido (organizacion/base_app.html) como todas las
    vistas de indicadores, organizacion y agenda."""
    request.session['persona_actual'] = persona['nombre']
    request.session['rol'] = persona['rol']
    request.session['usuario'] = persona['usuario']


def login_view(request):
    """Autentica contra la base de datos relacional (User y StaffProfile).
    Siempre muestra el formulario: entrar con otro usuario aquí reemplaza
    la sesión activa."""
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            persona = form.get_persona()
            user = form.get_user()
            if user:
                auth_login(request, user)
            _abrir_sesion(request, persona)
            messages.success(request, f"Bienvenido/a, {persona['nombre'].split()[0]}.")
            siguiente = request.GET.get('next')
            return redirect(siguiente or REDIRECT_TRAS_LOGIN)
    else:
        form = LoginForm()

    return render(request, 'cuentas/login.html', {'form': form})


def logout_view(request):
    """Cierra la sesión y redirige a la página pública."""
    auth_logout(request)
    request.session.flush()
    messages.info(request, 'Sesión cerrada correctamente.')
    return redirect('landing_page')


def registro_view(request):
    """Crea una persona nueva (User y StaffProfile) en la base de datos
    relacional e inicia sesión automáticamente al terminar."""
    if request.session.get('persona_actual') or getattr(request.user, 'is_authenticated', False):
        return redirect(REDIRECT_TRAS_LOGIN)

    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            persona = form.save()
            if hasattr(form, 'user'):
                auth_login(request, form.user)
            _abrir_sesion(request, persona)
            messages.success(request, 'Cuenta creada correctamente. ¡Bienvenido/a al SGR!')
            return redirect(REDIRECT_TRAS_LOGIN)
    else:
        form = RegistroForm()

    return render(request, 'cuentas/registro.html', {'form': form})


def recuperar_view(request):
    """Recuperación de contraseña en dos pasos:
    Paso 1: la persona se identifica por nombre de usuario o correo.
    Paso 2: define una nueva contraseña que se actualiza en User con hash seguro.
    """
    usuario_guardado = request.session.get(SESSION_KEY_RECUPERAR)

    # --- Paso 2: ya se identificó una cuenta, se define la nueva clave ---
    if usuario_guardado:
        user = get_user_model().objects.filter(username=usuario_guardado).first()
        if user is None:
            if SESSION_KEY_RECUPERAR in request.session:
                del request.session[SESSION_KEY_RECUPERAR]
            messages.error(request, 'La sesión de recuperación expiró. Intenta nuevamente.')
            return redirect('cuentas:recuperar')

        persona = {'usuario': user.username}

        if request.method == 'POST':
            form_password = NuevaPasswordForm(request.POST)
            if form_password.is_valid():
                user.set_password(form_password.cleaned_data['password1'])
                user.save()
                if SESSION_KEY_RECUPERAR in request.session:
                    del request.session[SESSION_KEY_RECUPERAR]
                messages.success(request, 'Contraseña actualizada. Ya puedes iniciar sesión.')
                return redirect('cuentas:login')
        else:
            form_password = NuevaPasswordForm()

        return render(request, 'cuentas/recuperar_password.html', {
            'paso': 2,
            'usuario': persona,
            'form_password': form_password,
        })

    # --- Paso 1: identificar la cuenta ---
    if request.method == 'POST':
        form_buscar = BuscarUsuarioForm(request.POST)
        if form_buscar.is_valid():
            persona = form_buscar.buscar_usuario()
            if persona:
                request.session[SESSION_KEY_RECUPERAR] = persona['usuario']
                return redirect('cuentas:recuperar')
            messages.error(request, 'No encontramos ninguna cuenta con ese usuario o correo.')
    else:
        form_buscar = BuscarUsuarioForm()

    return render(request, 'cuentas/recuperar_password.html', {
        'paso': 1,
        'form_buscar': form_buscar,
    })


@requiere_login
def home_view(request):
    """Escritorio principal del sistema tras iniciar sesión: resumen de
    compromisos de la agenda colectiva y accesos directos a los módulos."""
    nombre_usuario = request.session.get('persona_actual', '')
    if not nombre_usuario and getattr(request.user, 'is_authenticated', False):
        profile = getattr(request.user, 'staff_profile', None)
        nombre_usuario = profile.display_name if profile else (request.user.get_full_name() or request.user.username)

    compromisos_qs = Commitment.objects.select_related('owner', 'delegation').all()
    total_compromisos = compromisos_qs.count()
    pendientes = compromisos_qs.filter(
        status__in=[Commitment.Status.INGRESADO, Commitment.Status.PENDIENTE]
    ).count()
    en_proceso = compromisos_qs.filter(status=Commitment.Status.EN_PROCESO).count()
    realizados = compromisos_qs.filter(status=Commitment.Status.REALIZADO).count()

    mis_compromisos = []
    if nombre_usuario:
        mis_compromisos = list(
            compromisos_qs.filter(
                Q(owner__display_name__icontains=nombre_usuario)
                | Q(owner__user__username__iexact=nombre_usuario)
            )[:5]
        )

    contexto = {
        'nombre_usuario': nombre_usuario,
        'total_compromisos': total_compromisos,
        'pendientes': pendientes,
        'en_proceso': en_proceso,
        'realizados': realizados,
        'mis_compromisos': mis_compromisos,
    }
    return render(request, 'cuentas/home.html', contexto)
