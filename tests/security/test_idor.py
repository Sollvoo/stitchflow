"""
Tests de sécurité IDOR : JobOwnerMixin — protection cross-user.
"""
import pytest
from django.test import Client, override_settings

from factories import ConversionJobFactory, UserFactory


@pytest.mark.django_db
class TestJobOwnerMixin:
    """Vérifie les 5 cas d'accès définis dans JobOwnerMixin.dispatch()."""

    def setup_method(self):
        self.user_a = UserFactory()
        self.user_b = UserFactory()
        self.client_a = Client()
        self.client_b = Client()
        self.client_anon = Client()
        self.client_a.force_login(self.user_a)
        self.client_b.force_login(self.user_b)

    def _job_status_url(self, job_id):
        return f"/conversions/{job_id}/status/"

    def _job_api_url(self, job_id):
        return f"/conversions/{job_id}/api/status/"

    def _job_download_url(self, job_id):
        return f"/conversions/{job_id}/download/"

    # --- Cas 1 : user anonyme + job.user=None → bypass ---

    def test_anon_user_job_null_user_passes(self):
        job = ConversionJobFactory(user=None)
        response = self.client_anon.get(self._job_status_url(job.id))
        assert response.status_code != 403

    # --- Cas 2 : user anonyme + job.user=user_A → bypass anon ---

    def test_anon_user_job_owned_passes(self):
        job = ConversionJobFactory(user=self.user_a)
        response = self.client_anon.get(self._job_status_url(job.id))
        assert response.status_code != 403

    # --- Cas 3 : user A authentifié + job.user=None → desktop-mode bypass ---

    def test_auth_user_job_null_user_passes(self):
        job = ConversionJobFactory(user=None)
        response = self.client_a.get(self._job_status_url(job.id))
        assert response.status_code != 403

    # --- Cas 4 : user A authentifié + job.user=user_A → propriétaire → OK ---

    def test_auth_user_own_job_passes(self):
        job = ConversionJobFactory(user=self.user_a)
        response = self.client_a.get(self._job_status_url(job.id))
        assert response.status_code != 403

    # --- Cas 5 : user B authentifié + job.user=user_A → 403 ---

    def test_auth_user_cross_user_job_denied(self):
        job = ConversionJobFactory(user=self.user_a)
        response = self.client_b.get(self._job_status_url(job.id))
        assert response.status_code == 403

    def test_auth_user_cross_user_api_status_denied(self):
        job = ConversionJobFactory(user=self.user_a)
        response = self.client_b.get(self._job_api_url(job.id))
        assert response.status_code == 403

    def test_auth_user_cross_user_download_denied(self):
        job = ConversionJobFactory(user=self.user_a)
        response = self.client_b.get(self._job_download_url(job.id))
        assert response.status_code == 403

    def test_auth_user_cross_user_svg_editor_denied(self):
        """Tous les endpoints SVG editor appliquent JobOwnerMixin → 403 pour user B."""
        from conversions.models import ConversionJob
        job = ConversionJobFactory(
            user=self.user_a,
            status=ConversionJob.Status.AWAITING_SVG_VALIDATION,
        )
        url = f"/conversions/{job.id}/svg/remove-color/"
        response = self.client_b.post(url, {"color": "#ff0000"})
        assert response.status_code == 403

    def test_auth_user_cross_user_svg_validate_denied(self):
        from conversions.models import ConversionJob
        job = ConversionJobFactory(
            user=self.user_a,
            status=ConversionJob.Status.AWAITING_SVG_VALIDATION,
        )
        url = f"/conversions/{job.id}/svg/validate/"
        response = self.client_b.post(url)
        assert response.status_code == 403


@pytest.mark.django_db
class TestJobDetailPublicAccess:
    """JobDetailView n'a pas de check d'ownership → accessible publiquement par UUID."""

    def test_job_detail_accessible_by_any_user(self):
        user_a = UserFactory()
        user_b = UserFactory()
        job = ConversionJobFactory(user=user_a)
        client_b = Client()
        client_b.force_login(user_b)
        response = client_b.get(f"/conversions/{job.id}/")
        # 200 OK ou 302 redirect — jamais 403
        assert response.status_code in (200, 302)
        assert response.status_code != 403

    def test_job_detail_accessible_by_anon(self):
        user_a = UserFactory()
        job = ConversionJobFactory(user=user_a)
        client_anon = Client()
        response = client_anon.get(f"/conversions/{job.id}/")
        assert response.status_code in (200, 302)
        assert response.status_code != 403


@pytest.mark.django_db
class TestReconvertIDOR:
    """ReconvertView a une double protection IDOR (mixin + check explicite)."""

    def test_reconvert_cross_user_redirects(self):
        user_a = UserFactory()
        user_b = UserFactory()
        job = ConversionJobFactory(user=user_a)
        client_b = Client()
        client_b.force_login(user_b)
        response = client_b.post(f"/conversions/{job.id}/reconvert/")
        # La vue redirige vers history (check secondaire), ou le mixin lève 403
        assert response.status_code in (302, 403)
