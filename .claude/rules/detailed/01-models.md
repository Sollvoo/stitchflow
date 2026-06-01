---
description: Modèles Django — UUID, FileField, statuts, conventions
paths: ["**/models.py"]
priority: medium
tags: [backend, database]
---

# Modèles Django — StitchFlow

## ConversionJob

Modèle central. Conventions à respecter :

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

## Règles

- **UUID primary key** : toujours pour les modèles exposés en URL
- **`auto_now_add` / `auto_now`** : `created_at` et `updated_at` sur tous les modèles
- **`update_fields`** : toujours utiliser sur les `save()` partiels Celery pour éviter race conditions
- **`TextChoices`** : toujours, jamais de strings hardcodées pour les statuts
- **FileField** : `upload_to` avec sous-dossiers séparés (`conversions/uploads/`, `conversions/outputs/`)

## Migrations

- Toujours committer les migrations avec le code qui les génère
- `python src/manage.py makemigrations` puis `python src/manage.py migrate`
