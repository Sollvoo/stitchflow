"""
Tests d'intégration : JobOwnerMixin — cas de propriété les plus détaillés.
(Les tests IDOR principaux sont dans tests/security/test_idor.py)
"""
import pytest
from django.test import Client

from conversions.models import ConversionJob
from factories import ConversionJobFactory, UserFactory


@pytest.mark.django_db
def test_mixin_anon_user_job_null_owner_passes_status():
    """User anonyme + job.user=None → JobStatusView répond (pas 403)."""
    job = ConversionJobFactory(user=None)
    client = Client()
    response = client.get(f"/conversions/{job.id}/status/")
    assert response.status_code != 403


@pytest.mark.django_db
def test_mixin_auth_user_null_owner_passes():
    """User authentifié + job.user=None (mode desktop) → JobStatusView répond."""
    user = UserFactory()
    job = ConversionJobFactory(user=None)
    client = Client()
    client.force_login(user)
    response = client.get(f"/conversions/{job.id}/status/")
    assert response.status_code != 403


@pytest.mark.django_db
def test_mixin_owner_can_access_own_job():
    """Propriétaire du job → accès autorisé."""
    user = UserFactory()
    job = ConversionJobFactory(user=user)
    client = Client()
    client.force_login(user)
    response = client.get(f"/conversions/{job.id}/status/")
    assert response.status_code != 403


@pytest.mark.django_db
def test_mixin_non_owner_gets_403():
    """User différent du propriétaire → PermissionDenied → 403."""
    owner = UserFactory()
    other = UserFactory()
    job = ConversionJobFactory(user=owner)
    client = Client()
    client.force_login(other)
    response = client.get(f"/conversions/{job.id}/status/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_mixin_anon_user_can_access_owned_job():
    """User anonyme peut accéder à un job même si job.user est renseigné (bypass anon)."""
    user = UserFactory()
    job = ConversionJobFactory(user=user)
    client = Client()
    response = client.get(f"/conversions/{job.id}/status/")
    assert response.status_code != 403


@pytest.mark.django_db
def test_mixin_unknown_job_returns_404():
    """UUID inexistant → 404 (get_object_or_404)."""
    import uuid
    user = UserFactory()
    client = Client()
    client.force_login(user)
    response = client.get(f"/conversions/{uuid.uuid4()}/status/")
    assert response.status_code == 404
