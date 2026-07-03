from django.db import models


class WaitlistEmail(models.Model):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Email liste d'attente"
        verbose_name_plural = "Emails liste d'attente"
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.email
