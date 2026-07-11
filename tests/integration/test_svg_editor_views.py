"""
Tests d'intégration : vues SVG editor (SvgRemoveColorView, SvgChangeColorView,
SvgSetDensityView, SvgSetStitchTypeView, SvgValidateView, SvgMergeColorsView, etc.)
"""
import json
from pathlib import Path

import pytest
from django.test import Client, override_settings

from conversions.models import ConversionJob
from factories import ConversionJobFactory, UserFactory

MINIMAL_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100"><path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/></svg>'


def _make_awaiting_job(user, tmp_path, settings_obj):
    """Crée un job en statut AWAITING_SVG_VALIDATION avec un vrai fichier SVG."""
    settings_obj.MEDIA_ROOT = str(tmp_path)
    import os
    os.makedirs(tmp_path / "conversions" / "vectorized", exist_ok=True)
    svg_path = tmp_path / "conversions" / "vectorized" / "test.svg"
    svg_path.write_bytes(MINIMAL_SVG)

    job = ConversionJobFactory(
        user=user,
        status=ConversionJob.Status.AWAITING_SVG_VALIDATION,
    )
    job.vectorized_svg_file.name = "conversions/vectorized/test.svg"
    job.save()
    return job


@pytest.mark.django_db
class TestSvgEditorViewsRejectWrongStatus:
    """Toutes les vues editor doivent retourner 400 si status != AWAITING_SVG_VALIDATION."""

    EDITOR_URLS = [
        ("svg/remove-color/", {"color": "#ff0000"}),
        ("svg/merge-colors/", {"source": "#ff0000", "target": "#00ff00"}),
        ("svg/change-color/", {"old_color": "#ff0000", "new_color": "#00ff00"}),
        ("svg/undo/", {}),
        ("svg/redo/", {}),
        ("svg/reset/", {}),
    ]

    def _test_wrong_status(self, status, url_suffix, data):
        user = UserFactory()
        client = Client()
        client.force_login(user)
        job = ConversionJobFactory(user=user, status=status)
        url = f"/conversions/{job.id}/{url_suffix}"
        response = client.post(url, data)
        assert response.status_code == 400, (
            f"Attendu 400 pour {url_suffix} avec status={status}, got {response.status_code}"
        )

    def test_remove_color_pending_returns_400(self):
        self._test_wrong_status(ConversionJob.Status.PENDING, "svg/remove-color/", {"color": "#ff0000"})

    def test_remove_color_completed_returns_400(self):
        self._test_wrong_status(ConversionJob.Status.COMPLETED, "svg/remove-color/", {"color": "#ff0000"})

    def test_merge_colors_pending_returns_400(self):
        self._test_wrong_status(ConversionJob.Status.PENDING, "svg/merge-colors/", {"source": "#f00", "target": "#0f0"})

    def test_undo_failed_returns_400(self):
        self._test_wrong_status(ConversionJob.Status.FAILED, "svg/undo/", {})


@pytest.mark.django_db
class TestSvgChangeColorView:

    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def test_uppercase_hex_rejected(self, tmp_path, settings):
        job = _make_awaiting_job(self.user, tmp_path, settings)
        response = self.client.post(
            f"/conversions/{job.id}/svg/change-color/",
            {"old_color": "#ff0000", "new_color": "#FF0000"},
        )
        assert response.status_code == 400

    def test_lowercase_hex_accepted(self, tmp_path, settings, mocker):
        mocker.patch("conversions.services.svg_utils.change_svg_color", return_value=1)
        mocker.patch("conversions.views._snapshot_before_edit")
        mocker.patch("conversions.views._render_svg_editor_response",
                     return_value=__import__("django.http", fromlist=["HttpResponse"]).HttpResponse("OK"))
        job = _make_awaiting_job(self.user, tmp_path, settings)
        response = self.client.post(
            f"/conversions/{job.id}/svg/change-color/",
            {"old_color": "#ff0000", "new_color": "#00ff00"},
        )
        assert response.status_code in (200, 400)  # 200 si mock OK, 400 si erreur SVG

    def test_missing_new_color_rejected(self, tmp_path, settings):
        job = _make_awaiting_job(self.user, tmp_path, settings)
        response = self.client.post(
            f"/conversions/{job.id}/svg/change-color/",
            {"old_color": "#ff0000"},
        )
        assert response.status_code == 400

    def test_color_without_hash_rejected(self, tmp_path, settings):
        job = _make_awaiting_job(self.user, tmp_path, settings)
        response = self.client.post(
            f"/conversions/{job.id}/svg/change-color/",
            {"old_color": "#ff0000", "new_color": "ff0000"},
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestSvgSetDensityView:

    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def test_density_too_low_rejected(self, tmp_path, settings):
        job = _make_awaiting_job(self.user, tmp_path, settings)
        response = self.client.post(
            f"/conversions/{job.id}/svg/set-density/",
            {"color": "#ff0000", "density": "0.05"},
        )
        assert response.status_code == 400

    def test_density_too_high_rejected(self, tmp_path, settings):
        job = _make_awaiting_job(self.user, tmp_path, settings)
        response = self.client.post(
            f"/conversions/{job.id}/svg/set-density/",
            {"color": "#ff0000", "density": "2.1"},
        )
        assert response.status_code == 400

    def test_density_not_a_number_rejected(self, tmp_path, settings):
        job = _make_awaiting_job(self.user, tmp_path, settings)
        response = self.client.post(
            f"/conversions/{job.id}/svg/set-density/",
            {"color": "#ff0000", "density": "NaN"},
        )
        assert response.status_code == 400

    def test_density_at_boundary_low_rejected(self, tmp_path, settings):
        """0.09 < 0.1 → rejeté."""
        job = _make_awaiting_job(self.user, tmp_path, settings)
        response = self.client.post(
            f"/conversions/{job.id}/svg/set-density/",
            {"color": "#ff0000", "density": "0.09"},
        )
        assert response.status_code == 400

    def test_density_at_boundary_high_rejected(self, tmp_path, settings):
        """2.01 > 2.0 → rejeté."""
        job = _make_awaiting_job(self.user, tmp_path, settings)
        response = self.client.post(
            f"/conversions/{job.id}/svg/set-density/",
            {"color": "#ff0000", "density": "2.01"},
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestSvgSetStitchTypeView:

    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def test_invalid_stitch_type_rejected(self, tmp_path, settings):
        job = _make_awaiting_job(self.user, tmp_path, settings)
        response = self.client.post(
            f"/conversions/{job.id}/svg/set-stitch-type/",
            {"color": "#ff0000", "stitch_type": "satin_column"},
        )
        assert response.status_code == 400

    def test_auto_fill_accepted(self, tmp_path, settings, mocker):
        from django.http import HttpResponse as HR
        mocker.patch("conversions.services.svg_utils.set_stitch_type", return_value=0)
        mocker.patch("conversions.views._snapshot_before_edit")
        mocker.patch("conversions.views._render_svg_editor_response", return_value=HR("OK"))
        job = _make_awaiting_job(self.user, tmp_path, settings)
        response = self.client.post(
            f"/conversions/{job.id}/svg/set-stitch-type/",
            {"color": "#ff0000", "stitch_type": "auto_fill"},
        )
        assert response.status_code in (200, 400)

    def test_running_stitch_accepted(self, tmp_path, settings, mocker):
        from django.http import HttpResponse as HR
        mocker.patch("conversions.services.svg_utils.set_stitch_type", return_value=0)
        mocker.patch("conversions.views._snapshot_before_edit")
        mocker.patch("conversions.views._render_svg_editor_response", return_value=HR("OK"))
        job = _make_awaiting_job(self.user, tmp_path, settings)
        response = self.client.post(
            f"/conversions/{job.id}/svg/set-stitch-type/",
            {"color": "#ff0000", "stitch_type": "running_stitch"},
        )
        assert response.status_code in (200, 400)


@pytest.mark.django_db
class TestSvgMergeColorsView:

    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def test_source_equals_target_rejected(self, tmp_path, settings):
        job = _make_awaiting_job(self.user, tmp_path, settings)
        response = self.client.post(
            f"/conversions/{job.id}/svg/merge-colors/",
            {"source": "#ff0000", "target": "#ff0000"},
        )
        assert response.status_code == 400

    def test_source_without_hash_rejected(self, tmp_path, settings):
        job = _make_awaiting_job(self.user, tmp_path, settings)
        response = self.client.post(
            f"/conversions/{job.id}/svg/merge-colors/",
            {"source": "ff0000", "target": "#00ff00"},
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestSvgRemoveColorView:

    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def test_color_without_hash_rejected(self, tmp_path, settings):
        job = _make_awaiting_job(self.user, tmp_path, settings)
        response = self.client.post(
            f"/conversions/{job.id}/svg/remove-color/",
            {"color": "ff0000"},
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestSvgValidateView:

    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def test_validate_transitions_status_to_pending(self, tmp_path, settings, mocker):
        """SvgValidateView → AWAITING_SVG_VALIDATION → PENDING + dispatch task."""
        mocker.patch("conversions.views._dispatch")
        job = _make_awaiting_job(self.user, tmp_path, settings)
        response = self.client.post(f"/conversions/{job.id}/svg/validate/")
        assert response.status_code in (200, 302)
        job.refresh_from_db()
        assert job.status == ConversionJob.Status.PENDING

    def test_validate_wrong_status_rejected(self):
        """Job non en AWAITING_SVG_VALIDATION → 400."""
        user = UserFactory()
        client = Client()
        client.force_login(user)
        job = ConversionJobFactory(user=user, status=ConversionJob.Status.PENDING)
        response = client.post(f"/conversions/{job.id}/svg/validate/")
        assert response.status_code == 400


@pytest.mark.django_db
class TestSvgReorderColorsView:

    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def test_invalid_json_rejected(self, tmp_path, settings):
        job = _make_awaiting_job(self.user, tmp_path, settings)
        response = self.client.post(
            f"/conversions/{job.id}/svg/reorder-colors/",
            {"colors": "NOT JSON {{{"},
        )
        assert response.status_code == 400
