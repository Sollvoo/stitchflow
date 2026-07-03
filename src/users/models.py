from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

# Presets machines : needles = aiguilles physiques (scoring), max_threads = nombre
# de fils acceptable par design (les mono-aiguilles brodent le multicolore par
# re-enfilage — fusionner à 1 couleur serait destructeur).
MACHINE_PRESETS: dict[str, dict] = {
    'PR1050X': {'needles': 10, 'max_threads': 10, 'hoop_width_mm': 360, 'hoop_height_mm': 200, 'format': 'PES'},
    'PE800': {'needles': 1, 'max_threads': 8, 'hoop_width_mm': 130, 'hoop_height_mm': 180, 'format': 'PES'},
    'SE700': {'needles': 1, 'max_threads': 8, 'hoop_width_mm': 180, 'hoop_height_mm': 130, 'format': 'PES'},
    'MC500E': {'needles': 1, 'max_threads': 8, 'hoop_width_mm': 200, 'hoop_height_mm': 200, 'format': 'JEF'},
}

DEFAULT_MACHINE = {
    'model': 'PR1050X',
    'needles': 10,
    'max_threads': 10,
    'hoop_width_mm': 360,
    'hoop_height_mm': 200,
    'format': 'PES',
}


class UserProfile(models.Model):
    class MachineModel(models.TextChoices):
        PR1050X = 'PR1050X', 'Brother PR1050X (10 aiguilles)'
        PE800 = 'PE800', 'Brother PE800'
        SE700 = 'SE700', 'Brother SE700'
        MC500E = 'MC500E', 'Janome MC500E'
        CUSTOM = 'CUSTOM', 'Personnalisé'

    class MachineFormat(models.TextChoices):
        PES = 'PES', 'PES (Brother)'
        DST = 'DST', 'DST (Tajima)'
        JEF = 'JEF', 'JEF (Janome)'
        VP3 = 'VP3', 'VP3 (Husqvarna/Pfaff)'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    machine_model = models.CharField(
        max_length=20,
        choices=MachineModel.choices,
        default=MachineModel.PR1050X,
        verbose_name='Modèle de machine',
    )
    machine_needles = models.PositiveSmallIntegerField(
        default=10, verbose_name='Nombre d\'aiguilles'
    )
    machine_hoop_width_mm = models.PositiveSmallIntegerField(
        default=360, verbose_name='Largeur zone de broderie (mm)'
    )
    machine_hoop_height_mm = models.PositiveSmallIntegerField(
        default=200, verbose_name='Hauteur zone de broderie (mm)'
    )
    machine_format = models.CharField(
        max_length=4,
        choices=MachineFormat.choices,
        default=MachineFormat.PES,
        verbose_name='Format de fichier',
    )

    class Meta:
        verbose_name = 'Profil utilisateur'
        verbose_name_plural = 'Profils utilisateurs'

    def __str__(self) -> str:
        return f'Profil {self.user.username} — {self.machine_model}'

    @property
    def machine_max_threads(self) -> int:
        preset = MACHINE_PRESETS.get(self.machine_model)
        if preset:
            return preset['max_threads']
        return max(self.machine_needles, 8)

    def machine_params(self) -> dict:
        return {
            'model': self.machine_model,
            'needles': self.machine_needles,
            'max_threads': self.machine_max_threads,
            'hoop_width_mm': self.machine_hoop_width_mm,
            'hoop_height_mm': self.machine_hoop_height_mm,
            'format': self.machine_format,
        }


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
