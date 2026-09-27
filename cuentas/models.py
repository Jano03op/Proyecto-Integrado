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

    def __str__(self):
        return self.display_name
