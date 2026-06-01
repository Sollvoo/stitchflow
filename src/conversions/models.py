import uuid
from django.db import models


class ConversionJob(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'En attente'
        PROCESSING = 'processing', 'En cours'
        COMPLETED = 'completed', 'Terminé'
        FAILED = 'failed', 'Échoué'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_file = models.FileField(upload_to='conversions/uploads/')
    source_format = models.CharField(max_length=10, default='svg')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    error_message = models.TextField(blank=True)
    output_file = models.FileField(upload_to='conversions/outputs/', blank=True)
    preview_file = models.FileField(
        upload_to='conversions/previews/', blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"ConversionJob({self.id}, {self.status})"

    @property
    def is_terminal(self) -> bool:
        return self.status in (self.Status.COMPLETED, self.Status.FAILED)

    @property
    def original_filename(self) -> str:
        if self.original_file:
            return self.original_file.name.split('/')[-1]
        return ''
