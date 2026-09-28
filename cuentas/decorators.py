from functools import wraps

from django.shortcuts import redirect
from django.urls import reverse


def requiere_login(view_func):
    """
    Permite acceso tanto a sesiones con 'persona_actual' (legacy) como a usuarios
    autenticados mediante Django auth (ORM).
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        is_logged_in = getattr(request.user, "is_authenticated", False) or bool(request.session.get("persona_actual"))
        if not is_logged_in:
            return redirect(f"{reverse('cuentas:login')}?next={request.path}")
        return view_func(request, *args, **kwargs)
    return wrapper
