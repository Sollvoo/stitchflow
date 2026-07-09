from django_vite.core.asset_loader import (
    DEFAULT_APP_NAME,
    DjangoViteAppClient,
    DjangoViteConfig,
    ManifestClient,
)


class ReloadingManifestClient(ManifestClient):
    """Reload the Vite manifest on each lookup in local built-assets mode."""

    def get(self, path: str):
        if not self.dev_mode:
            parsed = self._parse_manifest()
            self._entries = parsed.entries
            self.legacy_polyfills_entry = parsed.legacy_polyfills_entry
        return super().get(path)


class ReloadingDjangoViteAppClient(DjangoViteAppClient):
    ManifestClient = ReloadingManifestClient

    def __init__(
        self, config: DjangoViteConfig, app_name: str = DEFAULT_APP_NAME
    ) -> None:
        super().__init__(config, app_name)
