"""
Tests d'intégration : HistoryView, ExportCSVView.
"""
from datetime import timedelta

import pytest
from django.test import Client, override_settings
from django.utils import timezone

from conversions.models import ConversionJob
from factories import ConversionJobFactory, UserFactory


@pytest.mark.django_db
class TestHistoryView:

    def setup_method(self):
        self.user_a = UserFactory()
        self.user_b = UserFactory()
        self.client_a = Client()
        self.client_b = Client()
        self.client_a.force_login(self.user_a)
        self.client_b.force_login(self.user_b)

    def test_anon_user_redirected(self):
        client = Client()
        response = client.get("/conversions/history/")
        assert response.status_code == 302
        assert "/auth/login/" in response["Location"]

    def test_authenticated_user_sees_own_jobs(self):
        ConversionJobFactory(user=self.user_a, original_filename="design_a")
        ConversionJobFactory(user=self.user_b, original_filename="design_b")
        response = self.client_a.get("/conversions/history/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "design_a" in content
        assert "design_b" not in content

    def test_status_filter_completed(self):
        ConversionJobFactory(user=self.user_a, status=ConversionJob.Status.COMPLETED)
        ConversionJobFactory(user=self.user_a, status=ConversionJob.Status.FAILED)
        response = self.client_a.get("/conversions/history/?status=completed")
        assert response.status_code == 200

    def test_status_filter_invalid_value_no_error(self):
        """Un statut invalide ne doit pas provoquer d'erreur 500."""
        ConversionJobFactory(user=self.user_a)
        response = self.client_a.get("/conversions/history/?status=invalid_hack_attempt")
        assert response.status_code == 200

    def test_format_filter_svg(self):
        ConversionJobFactory(user=self.user_a, source_format="svg")
        ConversionJobFactory(user=self.user_a, source_format="png")
        response = self.client_a.get("/conversions/history/?format=svg")
        assert response.status_code == 200

    def test_date_filter_7d(self):
        recent = ConversionJobFactory(user=self.user_a)
        old = ConversionJobFactory(user=self.user_a)
        # Forcer old.created_at à 10 jours en arrière
        ConversionJob.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )
        response = self.client_a.get("/conversions/history/?date=7d")
        assert response.status_code == 200

    def test_search_query(self):
        ConversionJobFactory(user=self.user_a, original_filename="mon_design_unique")
        ConversionJobFactory(user=self.user_a, original_filename="autre_design")
        response = self.client_a.get("/conversions/history/?q=unique")
        assert response.status_code == 200

    def test_pagination(self):
        """Plus de 24 jobs → pagination activée."""
        for i in range(26):
            ConversionJobFactory(user=self.user_a, original_filename=f"design_{i}")
        response = self.client_a.get("/conversions/history/")
        assert response.status_code == 200
        response_p2 = self.client_a.get("/conversions/history/?page=2")
        assert response_p2.status_code == 200


@pytest.mark.django_db
class TestExportCSVView:

    def setup_method(self):
        self.user_a = UserFactory()
        self.user_b = UserFactory()
        self.client_a = Client()
        self.client_a.force_login(self.user_a)

    def test_anon_redirected(self):
        response = Client().get("/conversions/history/export-csv/")
        assert response.status_code == 302

    def test_csv_contains_bom(self):
        """Le CSV doit commencer par un BOM UTF-8 (\xef\xbb\xbf)."""
        ConversionJobFactory(user=self.user_a)
        response = self.client_a.get("/conversions/history/export-csv/")
        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/csv")
        assert response.content[:3] == b"\xef\xbb\xbf"

    def test_csv_only_own_jobs(self):
        """Le CSV ne contient que les jobs de l'utilisateur connecté."""
        ConversionJobFactory(user=self.user_a, original_filename="mon_fichier")
        ConversionJobFactory(user=self.user_b, original_filename="fichier_b")
        response = self.client_a.get("/conversions/history/export-csv/")
        content = response.content.decode("utf-8-sig")  # strip BOM
        assert "mon_fichier" in content
        assert "fichier_b" not in content

    def test_csv_has_header_row(self):
        response = self.client_a.get("/conversions/history/export-csv/")
        content = response.content.decode("utf-8-sig")
        assert "ID" in content
        assert "Fichier" in content
        assert "Statut" in content
