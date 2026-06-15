import uuid
from django.db import models


class ConversionJob(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'En attente'
        PROCESSING = 'processing', 'En cours'
        AWAITING_SVG_VALIDATION = 'awaiting_svg_validation', 'Attente validation SVG'
        COMPLETED = 'completed', 'Terminé'
        FAILED = 'failed', 'Échoué'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_file = models.FileField(upload_to='conversions/uploads/')
    source_format = models.CharField(max_length=10, default='svg')
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    error_message = models.TextField(blank=True)
    output_file = models.FileField(upload_to='conversions/outputs/', blank=True)
    preview_file = models.FileField(
        upload_to='conversions/previews/', blank=True, null=True
    )
    original_filename = models.CharField(max_length=255, blank=True)
    target_width_mm = models.PositiveIntegerField(null=True, blank=True)
    conversion_metadata = models.JSONField(default=dict, blank=True)
    vectorized_svg_file = models.FileField(
        upload_to='conversions/vectorized/', blank=True, null=True
    )
    n_colors = models.PositiveSmallIntegerField(null=True, blank=True)
    remove_background = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"ConversionJob({self.id}, {self.status})"

    @property
    def is_terminal(self) -> bool:
        return self.status in (self.Status.COMPLETED, self.Status.FAILED)

