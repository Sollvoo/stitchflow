"""
Factory Boy factories pour les tests StitchFlow.
"""
import factory
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

from conversions.models import ConversionJob

MINIMAL_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100"><path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/></svg>'


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "password123")


class ConversionJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ConversionJob

    original_file = factory.LazyAttribute(
        lambda _: ContentFile(MINIMAL_SVG, name="test.svg")
    )
    status = ConversionJob.Status.PENDING
    source_format = "svg"
    original_filename = "test_design"
    user = None  # nullable par défaut (mode desktop)
