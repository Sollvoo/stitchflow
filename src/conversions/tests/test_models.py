from django.test import TestCase

from conversions.models import ConversionJob


class ConversionJobIsTerminalTest(TestCase):
    def _make_job(self, status: str) -> ConversionJob:
        job = ConversionJob.__new__(ConversionJob)
        job.status = status
        return job

    def test_completed_is_terminal(self):
        job = self._make_job(ConversionJob.Status.COMPLETED)
        self.assertTrue(job.is_terminal)

    def test_failed_is_terminal(self):
        job = self._make_job(ConversionJob.Status.FAILED)
        self.assertTrue(job.is_terminal)

    def test_pending_is_not_terminal(self):
        job = self._make_job(ConversionJob.Status.PENDING)
        self.assertFalse(job.is_terminal)

    def test_processing_is_not_terminal(self):
        job = self._make_job(ConversionJob.Status.PROCESSING)
        self.assertFalse(job.is_terminal)
