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
import subprocess
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings


class InkstitchError(Exception):
    """Erreur levée lors d'un problème avec la conversion Ink/Stitch."""
    pass


def humanize_inkstitch_error(raw_error: str) -> str:
    """Traduit les messages d'erreur bruts d'Ink/Stitch en messages lisibles en français."""
    lowered = raw_error.lower()

    if 'no stitchable' in lowered or 'stitchable elements' in lowered:
        return (
            'Le SVG ne contient pas d\'éléments brodables. '
            'Assurez-vous que vos formes ont un contour ou un remplissage.'
        )

    if 'filenotfounderror' in lowered or 'introuvable' in lowered or 'not found' in lowered:
        return 'Le service de conversion est temporairement indisponible. Réessayez dans quelques instants.'

    if 'timeoutexpired' in lowered or 'délai' in lowered or 'trop de temps' in lowered or 'timed out' in lowered:
        return (
            'La conversion a pris trop de temps (design trop complexe ?). '
            'Essayez de simplifier votre SVG.'
        )

    return raw_error


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
    executable = getattr(settings, 'INKSTITCH_EXECUTABLE', 'inkstitch')
    timeout = getattr(settings, 'INKSTITCH_TIMEOUT', 120)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Ink/Stitch écrit le ZIP sur stdout
    cmd = [
        executable,
        '--extension=zip',
        '--format-pes=True',
        str(input_svg_path),
    ]

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
            f"La conversion a dépassé le délai de {timeout} secondes."
        )

    if result.returncode != 0:
        stderr = result.stderr.decode('utf-8', errors='replace').strip()
        raise InkstitchError(
            f"Ink/Stitch a retourné le code {result.returncode}. "
            f"Stderr : {stderr or '(vide)'}"
        )

    zip_data = result.stdout
    if not zip_data:
        raise InkstitchError(
            "Ink/Stitch n'a produit aucune sortie. "
            "Vérifiez que le SVG contient des éléments brodables."
        )

    # Extraire le .pes depuis le ZIP en mémoire
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_zip:
        tmp_zip.write(zip_data)
        tmp_zip_path = Path(tmp_zip.name)

    try:
        pes_path = _extract_pes_from_zip(tmp_zip_path, output_dir, input_svg_path)
    finally:
        tmp_zip_path.unlink(missing_ok=True)

    return pes_path


def _extract_pes_from_zip(zip_path: Path, output_dir: Path, source_svg: Path) -> Path:
    """Extrait le premier fichier .pes trouvé dans le ZIP."""
    with zipfile.ZipFile(zip_path, 'r') as zf:
        pes_files = [name for name in zf.namelist() if name.lower().endswith('.pes')]

        if not pes_files:
            raise InkstitchError(
                "Aucun fichier .pes trouvé dans la sortie de Ink/Stitch. "
                f"Fichiers présents dans le ZIP : {zf.namelist()}"
            )

        pes_name = pes_files[0]
        # Nom de sortie basé sur le SVG source
        output_filename = source_svg.stem + '.pes'
        output_path = output_dir / output_filename

        with zf.open(pes_name) as src, open(output_path, 'wb') as dst:
            dst.write(src.read())

    return output_path
