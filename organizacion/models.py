from django.db import models


class Delegation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    name = models.CharField(max_length=150, unique=True)
    scope = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=8, choices=Status, default=Status.ACTIVE)

    def __str__(self):
        return self.name


class Position(models.Model):
    name = models.CharField(max_length=150, unique=True)

    def __str__(self):
        return self.name
