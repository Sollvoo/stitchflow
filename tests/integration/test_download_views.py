"""
Tests d'intégration : JobDownloadView, SvgDownloadView.
"""
import urllib.parse
from pathlib import Path

import pytest
from django.core.files.base import ContentFile
from django.test import Client, override_settings

from conversions.models import ConversionJob
from factories import ConversionJobFactory, UserFactory

MINIMAL_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm"><path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/></svg>'
MINIMAL_PES = b"#PES" + b"\x00" * 100


@pytest.mark.django_db
class TestJobDownloadView:

    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def _download_url(self, job):
        return f"/conversions/{job.id}/download/"

    def test_pending_job_returns_404(self):
        job = ConversionJobFactory(user=self.user, status=ConversionJob.Status.PENDING)
        response = self.client.get(self._download_url(job))
        assert response.status_code == 404

    def test_failed_job_returns_404(self):
        job = ConversionJobFactory(user=self.user, status=ConversionJob.Status.FAILED)
        response = self.client.get(self._download_url(job))
        assert response.status_code == 404

    def test_completed_no_output_file_returns_404(self):
        job = ConversionJobFactory(user=self.user, status=ConversionJob.Status.COMPLETED)
        job.output_file = None
        job.save()
        response = self.client.get(self._download_url(job))
        assert response.status_code == 404

    def test_completed_with_output_file_returns_200(self, tmp_path, settings):
        """Job terminé + fichier présent → 200 avec Content-Disposition."""
        settings.MEDIA_ROOT = str(tmp_path)
        import os
        os.makedirs(tmp_path / "conversions" / "outputs", exist_ok=True)

        pes_path = tmp_path / "conversions" / "outputs" / "test.pes"
        pes_path.write_bytes(MINIMAL_PES)

        job = ConversionJobFactory(
            user=self.user,
            status=ConversionJob.Status.COMPLETED,
            original_filename="mon_design",
        )
        job.output_file.name = "conversions/outputs/test.pes"
        job.save()

        response = self.client.get(self._download_url(job))
        assert response.status_code == 200
        disposition = response.get("Content-Disposition", "")
        assert "mon_design" in disposition
        assert ".pes" in disposition

    def test_content_disposition_rfc5987_accented(self, tmp_path, settings):
        """Nom avec accents → présence de filename*=UTF-8'' dans Content-Disposition."""
        settings.MEDIA_ROOT = str(tmp_path)
        import os
        os.makedirs(tmp_path / "conversions" / "outputs", exist_ok=True)

        pes_path = tmp_path / "conversions" / "outputs" / "test.pes"
        pes_path.write_bytes(MINIMAL_PES)

        job = ConversionJobFactory(
            user=self.user,
            status=ConversionJob.Status.COMPLETED,
            original_filename="Étoile brodée",
        )
        job.output_file.name = "conversions/outputs/test.pes"
        job.save()

        response = self.client.get(self._download_url(job))
        assert response.status_code == 200
        disposition = response.get("Content-Disposition", "")
        assert "filename*=UTF-8''" in disposition
        # Le nom encodé doit contenir les chars URL-encodés
        assert "%C3%89" in disposition or "%C3" in disposition  # É encodé

    def test_empty_original_filename_uses_fallback(self, tmp_path, settings):
        """Nom original vide → fallback 'stitch_<8 chars uuid>'."""
        settings.MEDIA_ROOT = str(tmp_path)
        import os
        os.makedirs(tmp_path / "conversions" / "outputs", exist_ok=True)

        pes_path = tmp_path / "conversions" / "outputs" / "test.pes"
        pes_path.write_bytes(MINIMAL_PES)

        job = ConversionJobFactory(
            user=self.user,
            status=ConversionJob.Status.COMPLETED,
            original_filename="",
        )
        job.output_file.name = "conversions/outputs/test.pes"
        job.save()

        response = self.client.get(self._download_url(job))
        assert response.status_code == 200
        disposition = response.get("Content-Disposition", "")
        assert "stitch_" in disposition


@pytest.mark.django_db
class TestSvgDownloadView:

    def setup_method(self):
        self.user = UserFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def _svg_download_url(self, job):
        return f"/conversions/{job.id}/svg/download/"

    def test_svg_download_fallback_to_original_for_svg_format(self, tmp_path, settings):
        """source_format='svg' sans vectorized_svg_file → fallback sur original_file."""
        settings.MEDIA_ROOT = str(tmp_path)
        import os
        os.makedirs(tmp_path / "conversions" / "uploads", exist_ok=True)

        svg_path = tmp_path / "conversions" / "uploads" / "test.svg"
        svg_path.write_bytes(MINIMAL_SVG)

        job = ConversionJobFactory(
            user=self.user,
            source_format="svg",
            original_filename="my_design",
        )
        job.original_file.name = "conversions/uploads/test.svg"
        job.save()

        response = self.client.get(self._svg_download_url(job))
        assert response.status_code == 200
        assert response["Content-Type"] == "image/svg+xml"

    def test_svg_download_no_file_returns_404(self):
        """Pas de vectorized_svg_file ni de fallback → 404."""
        job = ConversionJobFactory(user=self.user, source_format="png")
        job.vectorized_svg_file = None
        job.original_file = None
        job.save(update_fields=["vectorized_svg_file"])
        response = self.client.get(self._svg_download_url(job))
        assert response.status_code == 404
