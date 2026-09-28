from datetime import date
from decimal import Decimal, DecimalException

from django.shortcuts import redirect, render

from cuentas.models import StaffProfile
from organizacion.models import Position
from .models import Period, StaffTarget


def _get_user_role(request, profile=None):
    if request.session.get("rol"):
        return request.session.get("rol")
    if getattr(request.user, "is_authenticated", False):
        if request.user.is_superuser or request.user.is_staff:
            return "administrador"
        prof = profile or getattr(request.user, "staff_profile", None)
        if prof and prof.legacy_role:
            return prof.legacy_role.lower()
    if profile and profile.legacy_role:
        return profile.legacy_role.lower()
    return "funcionario"


def _obtener_persona(request):
    """Resolve the active StaffProfile from session or authenticated user.

    If session has 'persona_actual', find the StaffProfile by display_name.
    If authenticated, use user.staff_profile if available.
    Fallback to the first existing StaffProfile or an in-memory instance.
    """
    nombre_guardado = request.session.get("persona_actual")
    if nombre_guardado:
        profile = (
            StaffProfile.objects.select_related("delegation", "position", "user")
            .filter(display_name=nombre_guardado)
            .first()
        )
        if profile:
            return profile
        return StaffProfile(
            display_name=nombre_guardado,
            legacy_role=request.session.get("rol", "funcionario"),
        )

    if getattr(request.user, "is_authenticated", False):
        profile = getattr(request.user, "staff_profile", None)
        if profile:
            request.session["persona_actual"] = profile.display_name
            request.session["rol"] = profile.legacy_role or (
                "administrador" if request.user.is_superuser else "funcionario"
            )
            return profile

    first_profile = (
        StaffProfile.objects.select_related("delegation", "position", "user").first()
    )
    if first_profile:
        request.session["persona_actual"] = first_profile.display_name
        request.session["rol"] = first_profile.legacy_role or "funcionario"
        return first_profile

    return StaffProfile(
        display_name="Usuario Demo",
        legacy_role=request.session.get("rol", "funcionario"),
    )


def landing(request):
    hola = _obtener_persona(request)
    rol_actual = _get_user_role(request, hola)

    if rol_actual in ["delegado", "coordinador", "administrador"]:
        resumen_equipo = []
        profiles = (
            StaffProfile.objects.select_related("delegation", "position")
            .prefetch_related("targets__item")
            .all()
        )

        for persona in profiles:
            items = list(persona.targets.all())
            if not items:
                continue

            porcentajes = []
            for item in items:
                if item.goal and item.goal > 0:
                    porcentajes.append((item.avance / item.goal) * Decimal("100"))
                else:
                    porcentajes.append(Decimal("0"))

            if porcentajes:
                promedio = sum(porcentajes) / Decimal(len(porcentajes))
                resumen_equipo.append({
                    "nombre": persona.nombre,
                    "cargo": persona.cargo,
                    "delegacion": persona.delegacion,
                    "promedio": promedio,
                })

        resumen_equipo.sort(key=lambda x: x["promedio"])
        peores_del_equipo = resumen_equipo[:3]

        return render(
            request,
            "indicadores/landing_monitor.html",
            {
                "simulacion": hola,
                "peores_del_equipo": peores_del_equipo,
                "rol": rol_actual,
            },
        )
    else:
        peor = list(hola.items)
        peor.sort(key=lambda x: x.porcentaje)

        return render(
            request,
            "indicadores/landinginterno.html",
            {
                "simulacion": hola,
                "actividades": peor,
                "rol": rol_actual,
            },
        )


def _get_active_period_and_meta():
    period = Period.objects.filter(status=Period.Status.ACTIVE).first()
    if not period:
        period = Period.objects.order_by("-starts_on").first()

    today = date.today()
    if period and period.total_days > 0:
        elapsed = period.elapsed_days(today)
        metaesperada = (Decimal(elapsed) / Decimal(period.total_days)) * Decimal("100")
    else:
        metaesperada = Decimal("50")

    periodo_dict = {
        "inicio": period.starts_on.isoformat() if period else "",
        "termino": period.ends_on.isoformat() if period else "",
        "Calculo": {
            "totaldias": period.total_days if period else 0,
            "transcurrido": period.elapsed_days(today) if period else 0,
            "restante": (period.total_days - period.elapsed_days(today)) if period else 0,
            "meta": float(metaesperada),
        }
        if period
        else {"totaldias": 0, "transcurrido": 0, "restante": 0, "meta": 50.0},
    }
    return period, metaesperada, periodo_dict


def dashboard(request):
    if "persona_actual" not in request.session and not getattr(
        request.user, "is_authenticated", False
    ):
        return redirect("landing")

    hola = _obtener_persona(request)
    rol_actual = _get_user_role(request, hola)
    _, metaesperada, periodo_dict = _get_active_period_and_meta()

    personas = list(
        StaffProfile.objects.select_related("delegation", "position")
        .prefetch_related("targets__item")
        .order_by("display_name")
    )

    for persona in personas:
        targets = list(persona.targets.all())
        for actividad in targets:
            resultado = actividad.porcentaje
            if resultado >= metaesperada:
                actividad.semaforo = "verde"
            elif resultado >= metaesperada * Decimal("0.6"):
                actividad.semaforo = "ambar"
            else:
                actividad.semaforo = "rojo"
        persona.items = targets

    return render(
        request,
        "indicadores/dashboard.html",
        {
            "periodo": periodo_dict,
            "personas": personas,
            "rol": rol_actual,
        },
    )


def logueo(request):
    if "persona_actual" not in request.session and not getattr(
        request.user, "is_authenticated", False
    ):
        return redirect("landing")

    hola = _obtener_persona(request)
    rol_actual = _get_user_role(request, hola)
    _, metaesperada, _ = _get_active_period_and_meta()

    targets = list(hola.targets.select_related("item").all()) if hola.pk else []
    for actividad in targets:
        resultado = actividad.porcentaje
        actividad.ponderado_cumplimiento = (
            actividad.weight_percent * resultado
        ) / Decimal("100")
        if resultado >= metaesperada:
            actividad.semaforo = "verde"
        elif resultado >= metaesperada * Decimal("0.6"):
            actividad.semaforo = "ambar"
        else:
            actividad.semaforo = "rojo"

    targets.sort(key=lambda x: x.porcentaje)
    hola.items = targets

    return render(
        request,
        "indicadores/indicador.html",
        {
            "simulacion": hola,
            "rol": rol_actual,
        },
    )


def resetear(request):
    request.session.flush()
    return redirect("landing")


def mi_cuenta(request):
    if "persona_actual" not in request.session and not getattr(
        request.user, "is_authenticated", False
    ):
        return redirect("landing")

    hola = _obtener_persona(request)
    inicial = hola.nombre[0].upper() if hola.nombre else "U"
    rol_actual = _get_user_role(request, hola)

    return render(
        request,
        "indicadores/mi_cuenta.html",
        {
            "simulacion": hola,
            "inicial": inicial,
            "rol": rol_actual,
        },
    )


def configurar_metas(request):
    if "persona_actual" not in request.session and not getattr(
        request.user, "is_authenticated", False
    ):
        return redirect("landing")

    hola = _obtener_persona(request)
    rol_actual = _get_user_role(request, hola)

    if rol_actual not in ["administrador", "coordinador"]:
        return redirect("landing")

    if request.method == "POST":
        cargo_seleccionado = request.POST.get("cargo")
        if cargo_seleccionado:
            targets_to_update = (
                StaffTarget.objects.filter(staff__position__name=cargo_seleccionado)
                .exclude(period__status=Period.Status.CLOSED)
                .select_related("item")
            )
            for target in targets_to_update:
                nueva_meta = request.POST.get(f"meta_{target.item.name}")
                nuevo_ponderador = request.POST.get(f"ponderador_{target.item.name}")
                changed = False
                if nueva_meta is not None and nueva_meta.strip() != "":
                    try:
                        target.goal = Decimal(nueva_meta)
                        changed = True
                    except (ValueError, TypeError, DecimalException):
                        pass
                if nuevo_ponderador is not None and nuevo_ponderador.strip() != "":
                    try:
                        target.weight_percent = Decimal(nuevo_ponderador)
                        changed = True
                    except (ValueError, TypeError, DecimalException):
                        pass
                if changed:
                    target.save()

    cargos_vistos = {}
    positions = (
        Position.objects.filter(staff__targets__isnull=False).distinct().order_by("name")
    )
    for pos in positions:
        sample_staff = StaffProfile.objects.filter(
            position=pos, targets__isnull=False
        ).first()
        if sample_staff:
            targets = list(
                sample_staff.targets.select_related("item").order_by("item__name")
            )
            if targets:
                cargos_vistos[pos.name] = targets

    return render(
        request,
        "indicadores/configurar_metas.html",
        {
            "rol": rol_actual,
            "cargos_vistos": cargos_vistos,
        },
    )
