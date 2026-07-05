"""
Service d'intégration avec Ink/Stitch CLI.

Ink/Stitch peut être exécuté en ligne de commande :
    ./inkstitch --extension=zip --format-pes=True input.svg > output.zip

Documentation : https://inkstitch.org/docs/command-line

Sur macOS, après installation de l'extension Inkscape, l'exécutable se trouve
typiquement dans le répertoire d'extensions Inkscape.

Configurer le chemin via la variable d'environnement INKSTITCH_EXECUTABLE
dans votre fichier .env, ou laisser 'inkstitch' si l'exécutable est dans le PATH.
"""

import logging
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


class InkstitchError(Exception):
    """Erreur levée lors d'un problème avec la conversion Ink/Stitch."""

    pass


def humanize_inkstitch_error(raw_error: str) -> str:
    """Traduit les messages d'erreur bruts d'Ink/Stitch en messages lisibles en français."""
    lowered = raw_error.lower()

    if "no stitchable" in lowered or "stitchable elements" in lowered:
        return (
            "Le SVG ne contient pas d'éléments brodables. "
            "Assurez-vous que vos formes ont un contour ou un remplissage."
        )

    if (
        "filenotfounderror" in lowered
        or "introuvable" in lowered
        or "not found" in lowered
    ):
        return (
            "Le service de conversion est temporairement indisponible. "
            "Réessayez dans quelques instants."
        )

    if (
        "timeoutexpired" in lowered
        or "délai" in lowered
        or "trop de temps" in lowered
        or "timed out" in lowered
    ):
        return (
            "La conversion a pris trop de temps (design trop complexe ?). "
            "Essayez de simplifier votre SVG."
        )

    return raw_error


_CACHE_CORRUPTION_MARKER = "database disk image is malformed"


def _purge_inkstitch_stitch_plan_cache() -> bool:
    """
    Supprime le cache de plans de broderie d'Ink/Stitch (diskcache SQLite).

    Un cache corrompu fait échouer TOUTES les conversions silencieusement
    (exit 0, ZIP vide, erreur sqlite3 sur stderr). Le cache est régénéré
    automatiquement par Ink/Stitch au prochain run.
    """
    candidates: list[Path] = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(
            Path(local_app_data) / "inkstitch" / "inkstitch" / "cache" / "stitch_plan"
        )
    candidates.append(Path.home() / ".cache" / "inkstitch" / "stitch_plan")

    for cache_dir in candidates:
        if cache_dir.is_dir():
            try:
                shutil.rmtree(cache_dir)
                logger.warning(
                    "Cache Ink/Stitch corrompu purgé : %s — nouvelle tentative.",
                    cache_dir,
                )
                return True
            except OSError as exc:
                logger.warning("Purge du cache Ink/Stitch impossible (%s) : %s", cache_dir, exc)
    return False


def convert_svg_to_pes(input_svg_path: Path, output_dir: Path) -> Path:
    """
    Convertit un fichier SVG en fichier PES via Ink/Stitch CLI.

    Ink/Stitch produit un ZIP contenant le .pes (et éventuellement d'autres
    formats). Cette fonction extrait le .pes et le dépose dans output_dir.

    Args:
        input_svg_path: Chemin absolu vers le fichier SVG source.
        output_dir: Répertoire de destination pour le fichier .pes généré.

    Returns:
        Chemin absolu du fichier .pes généré.

    Raises:
        InkstitchError: Si inkstitch échoue ou si le .pes n'est pas trouvé dans le ZIP.
        FileNotFoundError: Si l'exécutable inkstitch n'est pas trouvé.
    """
    executable = getattr(settings, "INKSTITCH_EXECUTABLE", "inkstitch")
    timeout = getattr(settings, "INKSTITCH_TIMEOUT", 120)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Ink/Stitch écrit le ZIP sur stdout
    cmd = [
        executable,
        "--extension=zip",
        "--format-pes=True",
        str(input_svg_path),
    ]

    for attempt in range(2):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            raise FileNotFoundError(
                f"L'exécutable inkstitch est introuvable : '{executable}'. "
                "Consultez CLAUDE.md pour les instructions d'installation."
            )
        except subprocess.TimeoutExpired:
            raise InkstitchError(
                f"La conversion a dépassé le délai de {timeout} secondes. "
                "Essayez de réduire la taille ou le nombre de couleurs."
            )

        stderr = result.stderr.decode("utf-8", errors="replace").strip()

        # Cache diskcache corrompu : Ink/Stitch sort en exit 0 avec un ZIP
        # vide et l'erreur sqlite3 sur stderr → purge + un seul retry.
        if (
            attempt == 0
            and not result.stdout
            and _CACHE_CORRUPTION_MARKER in stderr
            and _purge_inkstitch_stitch_plan_cache()
        ):
            continue

        break

    if result.returncode != 0:
        raise InkstitchError(
            f"Ink/Stitch a retourné le code {result.returncode}. "
            f"Stderr : {stderr or '(vide)'}"
        )

    zip_data = result.stdout
    if not zip_data:
        if _CACHE_CORRUPTION_MARKER in stderr:
            raise InkstitchError(
                "Le cache interne d'Ink/Stitch est corrompu et n'a pas pu être "
                "réparé automatiquement. Supprimez le dossier "
                "'inkstitch/cache/stitch_plan' dans AppData\\Local puis réessayez."
            )
        raise InkstitchError(
            "Ink/Stitch n'a produit aucune sortie. "
            "Vérifiez que le SVG contient des éléments brodables."
        )

    # Extraire le .pes depuis le ZIP en mémoire
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_zip:
        tmp_zip.write(zip_data)
        tmp_zip_path = Path(tmp_zip.name)

    try:
        pes_path = _extract_pes_from_zip(tmp_zip_path, output_dir, input_svg_path)
    finally:
        tmp_zip_path.unlink(missing_ok=True)

    return pes_path


_SUPPORTED_EXPORT_FORMATS = frozenset(["DST", "JEF", "VP3"])


def convert_pes_to_format(pes_path: Path, target_format: str) -> Path:
    """
    Convertit un PES vers un autre format machine via pyembroidery.

    Le PES reste la source de vérité (preview + métadonnées) ; le fichier
    cible est écrit à côté avec l'extension du format.

    Args:
        pes_path: Chemin du fichier PES source.
        target_format: 'DST', 'JEF' ou 'VP3'.

    Returns:
        Chemin du fichier converti.

    Raises:
        InkstitchError: Format non supporté ou conversion échouée.
    """
    import pyembroidery

    fmt = target_format.strip().upper()
    if fmt not in _SUPPORTED_EXPORT_FORMATS:
        raise InkstitchError(f"Format d'export non supporté : {target_format}")

    output_path = pes_path.with_suffix(f".{fmt.lower()}")
    try:
        pattern = pyembroidery.read(str(pes_path))
        if pattern is None:
            raise InkstitchError(f"Lecture du PES impossible : {pes_path.name}")
        pyembroidery.write(pattern, str(output_path))
    except InkstitchError:
        raise
    except Exception as exc:
        raise InkstitchError(f"Export {fmt} échoué : {exc}") from exc

    if not output_path.exists():
        raise InkstitchError(f"Export {fmt} : fichier non produit")

    return output_path


def _extract_pes_from_zip(zip_path: Path, output_dir: Path, source_svg: Path) -> Path:
    """Extrait le premier fichier .pes trouvé dans le ZIP."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        pes_files = [name for name in zf.namelist() if name.lower().endswith(".pes")]

        if not pes_files:
            raise InkstitchError(
                "Aucun fichier .pes trouvé dans la sortie de Ink/Stitch. "
                f"Fichiers présents dans le ZIP : {zf.namelist()}"
            )

        pes_name = pes_files[0]
        # Nom de sortie basé sur le SVG source
        output_filename = source_svg.stem + ".pes"
        output_path = output_dir / output_filename

        with zf.open(pes_name) as src, open(output_path, "wb") as dst:
            dst.write(src.read())

    return output_path
