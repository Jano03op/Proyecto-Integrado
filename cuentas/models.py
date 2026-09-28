from django.conf import settings
from django.db import models

from organizacion.models import Delegation, Position


class StaffProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="staff_profile",
    )
    delegation = models.ForeignKey(
        Delegation, on_delete=models.PROTECT, null=True, blank=True, related_name="staff"
    )
    position = models.ForeignKey(
        Position, on_delete=models.PROTECT, null=True, blank=True, related_name="staff"
    )
    display_name = models.CharField(max_length=150)
    legacy_role = models.CharField(max_length=150, blank=True)

    @property
    def nombre(self):
        return self.display_name

    @property
    def cargo(self):
        return self.position.name if self.position else "Sin cargo asignado"

    @property
    def estado(self):
        if self.user:
            return "Activo" if self.user.is_active else "Inactivo"
        return "Activo"

    @property
    def iniciales(self):
        parts = self.display_name.strip().split()
        if not parts:
            return "--"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[1][0]).upper()

    @property
    def es_verificador(self):
        return "verificador" in (self.legacy_role or "").lower()

    @property
    def delegacion(self):
        return self.delegation.name if self.delegation else ""

    @property
    def rol(self):
        return self.legacy_role or "funcionario"

    @property
    def correo(self):
        if self.user and self.user.email:
            return self.user.email
        return ""

    @property
    def items(self):
        if hasattr(self, "_cached_items"):
            return self._cached_items
        return list(self.targets.select_related("item").all())

    @items.setter
    def items(self, value):
        self._cached_items = value

    def __str__(self):
        return self.display_name
