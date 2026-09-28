from django.db import models


class Delegation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    name = models.CharField(max_length=150, unique=True)
    scope = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=8, choices=Status, default=Status.ACTIVE)

    @property
    def nombre(self):
        return self.name

    @property
    def ambito(self):
        return self.scope

    @property
    def estado(self):
        return "Activa" if self.status == self.Status.ACTIVE else "Inactiva"

    @property
    def n_funcionarios(self):
        return getattr(self, "_n_funcionarios", None) or self.staff.count()

    @n_funcionarios.setter
    def n_funcionarios(self, value):
        self._n_funcionarios = value

    def __str__(self):
        return self.name


class Position(models.Model):
    name = models.CharField(max_length=150, unique=True)

    def __str__(self):
        return self.name
