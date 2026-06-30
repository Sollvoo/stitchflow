---
description: Modeles Django - UUID, FileField, statuts, conventions
paths: ["**/models.py"]
priority: medium
tags: [backend, database]
---

# Modeles Django - StitchFlow

## ConversionJob

Modele central. Conventions a respecter :

```python
class ConversionJob(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending'
        PROCESSING = 'processing'
        COMPLETED = 'completed'
        FAILED = 'failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # ...

    @property
    def is_terminal(self) -> bool:
        return self.status in (self.Status.COMPLETED, self.Status.FAILED)
```

## Regles

- **UUID primary key** : toujours pour les modeles exposes en URL
- **`auto_now_add` / `auto_now`** : `created_at` et `updated_at` sur tous les modeles
- **`update_fields`** : toujours utiliser sur les `save()` partiels Celery pour eviter les race conditions
- **`TextChoices`** : toujours, jamais de strings hardcodees pour les statuts
- **FileField** : `upload_to` avec sous-dossiers separes (`conversions/uploads/`, `conversions/outputs/`)

## Migrations

- Toujours committer les migrations avec le code qui les genere
- `python src/manage.py makemigrations` puis `python src/manage.py migrate`
