#!/usr/bin/env python3
"""
Benchmark autonome du pipeline StitchFlow — sans Celery, sans HTTP.
Appelle directement les fonctions de service sur 12 cas de test représentatifs.

Usage :
    source .venv/bin/activate
    python tests/run_benchmark.py [--tests T01,T08] [--output results.json]

Résultats : JSON dans tests/benchmark_results_YYYYMMDD_HHMMSS.json + table stdout.
"""
import argparse
import json
import logging
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Setup Django (sans Celery)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'src'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stitchflow.settings')

import django
django.setup()

# ---------------------------------------------------------------------------
# Imports services
# ---------------------------------------------------------------------------
from conversions.services.inkstitch import convert_svg_to_pes, InkstitchError
from conversions.services.pdf_processing import (
    GradientNotSupportedError,
    PDFExtractionError,
    extract_vector_svg_from_pdf,
    is_vector_pdf_svg,
    postprocess_vector_svg,
)
from conversions.services.png_processing import (
    PNGValidationError,
    convert_pdf_to_png,
    convert_to_png,
    preprocess_image,
    remove_background,
    validate_png,
    vectorize_to_svg,
)
from conversions.services.previews import extract_pes_metadata
from conversions.services.svg_utils import (
    _count_svg_unique_fills,
    filter_micro_paths,
    force_max_svg_colors,
    group_paths_by_color,
    normalize_stroke_only_paths,
    remove_background_fill,
    reorder_svg_paths_for_minimal_jumps,
    scale_svg_to_width_mm,
)
from conversions.services.thread_color import snap_svg_colors_to_brother_palette
from conversions.services.validation import SVGValidationError, validate_svg_content

# ---------------------------------------------------------------------------
# Configuration des 12 tests
# ---------------------------------------------------------------------------
TESTS_DIR = ROOT / 'tests' / 'manual'

TESTS: list[dict[str, Any]] = [
    {
        'test_id': 'T01',
        'file': 'png/06-logo-monochrome-blanc.png',
        'format': 'png',
        'n_colors': 2,
        'remove_bg': True,
        'target_width_mm': 80,
        'description': 'Logo monochrome PNG — baseline facile',
    },
    {
        'test_id': 'T02',
        'file': 'png/03-logo-multicolore.png',
        'format': 'png',
        'n_colors': 5,
        'remove_bg': False,
        'target_width_mm': 80,
        'description': 'Logo 4-5 couleurs PNG',
    },
    {
        'test_id': 'T03',
        'file': 'png/07-ecusson-12couleurs.png',
        'format': 'png',
        'n_colors': 10,
        'remove_bg': False,
        'target_width_mm': 100,
        'description': 'Écusson 10+ couleurs PNG — difficile',
    },
    {
        'test_id': 'T04',
        'file': 'png/08-texte-fond-colore.png',
        'format': 'png',
        'n_colors': 4,
        'remove_bg': False,
        'target_width_mm': 60,
        'description': 'Texte sur fond coloré PNG — texte fin',
    },
    {
        'test_id': 'T05',
        'file': 'png/09-photo-complexe-bruit.png',
        'format': 'png',
        'n_colors': 8,
        'remove_bg': True,
        'target_width_mm': 100,
        'description': 'Photo complexe PNG — ceiling vectorisation',
    },
    {
        'test_id': 'T06',
        'file': 'jpeg/12-logo-formes-simple.jpg',
        'format': 'jpeg',
        'n_colors': 6,
        'remove_bg': False,
        'target_width_mm': 80,
        'description': 'Logo simple JPEG',
    },
    {
        'test_id': 'T07',
        'file': 'webp/test-logo.webp',
        'format': 'webp',
        'n_colors': 5,
        'remove_bg': False,
        'target_width_mm': 80,
        'description': 'Logo WebP',
    },
    {
        'test_id': 'T08',
        'file': 'svg/01-circle-simple.svg',
        'format': 'svg',
        'n_colors': None,
        'remove_bg': False,
        'target_width_mm': 80,
        'description': 'SVG simple monocolor — baseline SVG',
    },
    {
        'test_id': 'T09',
        'file': 'svg/07-logo-atelier-8couleurs.svg',
        'format': 'svg',
        'n_colors': None,
        'remove_bg': False,
        'target_width_mm': 100,
        'description': 'SVG multi-couleurs 8 fils',
    },
    {
        'test_id': 'T10',
        'file': 'svg/06-text-outline.svg',
        'format': 'svg',
        'n_colors': None,
        'remove_bg': False,
        'target_width_mm': 80,
        'description': 'SVG texte en contours — stroke-only',
    },
    {
        'test_id': 'T11',
        'file': 'pdf/test-logo.pdf',
        'format': 'pdf',
        'n_colors': 6,
        'remove_bg': False,
        'target_width_mm': 100,
        'description': 'PDF vectoriel',
    },
    {
        'test_id': 'T12',
        'file': 'pdf/test-scanned-pdf.pdf',
        'format': 'pdf',
        'n_colors': 4,
        'remove_bg': False,
        'target_width_mm': 80,
        'description': 'PDF scanné (raster)',
    },
    {
        'test_id': 'T13',
        'file': 'svg/08-texte-fin-contours.svg',
        'format': 'svg',
        'n_colors': None,
        'remove_bg': False,
        'target_width_mm': 60,
        'description': 'SVG texte très fin en contours — Hard (lisibilité machine)',
    },
    {
        'test_id': 'T14',
        'file': 'pdf/test-vectoriel-complexe.pdf',
        'format': 'pdf',
        'n_colors': 6,
        'remove_bg': False,
        'target_width_mm': 120,
        'description': 'PDF vectoriel complexe grand format — Hard',
    },
    {
        'test_id': 'T15',
        'file': 'png/11-logo-transparent-alpha.png',
        'format': 'png',
        'n_colors': 4,
        'remove_bg': False,
        'target_width_mm': 80,
        'description': 'Logo PNG canal alpha (RGBA 600x400) — Medium',
    },
    {
        'test_id': 'T16',
        'file': 'pdf/logo gravo clés.pdf',
        'format': 'pdf',
        'n_colors': 6,
        'remove_bg': False,
        'target_width_mm': 100,
        'description': 'PDF complexe lourd 1.37MB — Hard',
    },
]


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------

def _apply_svg_postprocess(
    svg_path: Path,
    target_width_mm: int,
    remove_bg: bool,
    n_colors_requested: int | None,
) -> tuple[Path, Path | None]:
    """
    Applique le pipeline SVG commun (filtrage, reorder, scale, snap, normalize).
    Retourne (svg_to_convert, scaled_path_to_cleanup).
    scaled_path_to_cleanup doit être supprimé par l'appelant.
    """
    validate_svg_content(svg_path)

    if remove_bg:
        remove_background_fill(svg_path)

    filter_micro_paths(svg_path, target_width_mm)
    reorder_svg_paths_for_minimal_jumps(svg_path)
    group_paths_by_color(svg_path)

    scaled_path: Path | None = None
    svg_to_convert = svg_path
    if target_width_mm:
        scaled_path = scale_svg_to_width_mm(svg_path, target_width_mm)
        svg_to_convert = scaled_path

    force_max_svg_colors(svg_to_convert, max_colors=10)
    try:
        snap_svg_colors_to_brother_palette(svg_to_convert)
    except Exception:
        pass  # palette Brother absente → pas bloquant

    group_paths_by_color(svg_to_convert)
    normalize_stroke_only_paths(svg_to_convert)

    return svg_to_convert, scaled_path


def _run_raster_pipeline(
    input_path: Path,
    source_format: str,
    n_colors: int,
    remove_bg: bool,
    target_width_mm: int,
    tmp_dir: Path,
) -> dict[str, Any]:
    """Pipeline PNG/JPEG/WebP → SVG → PES."""
    output_dir = tmp_dir / 'output'
    output_dir.mkdir()

    tmp_pngs: list[Path] = []
    scaled_path: Path | None = None

    try:
        # 1. Conversion initiale si nécessaire
        if source_format in ('jpeg', 'webp'):
            png_path = convert_to_png(input_path)
            tmp_pngs.append(png_path)
        else:
            png_path = input_path

        # 2. Validation + prétraitement
        validate_png(png_path)
        processed = preprocess_image(png_path)
        tmp_pngs.append(processed)

        if remove_bg:
            processed = remove_background(processed)
            tmp_pngs.append(processed)

        # 3. Vectorisation
        svg_path = vectorize_to_svg(processed, n_colors=n_colors)
        tmp_pngs.append(svg_path)  # nettoyage groupé

        # 4. Post-traitement SVG
        svg_to_convert, scaled_path = _apply_svg_postprocess(
            svg_path,
            target_width_mm=target_width_mm,
            remove_bg=True,  # supprimer fond blanc vectorisé pour source raster
            n_colors_requested=n_colors,
        )

        # 5. Conversion PES
        pes_path = convert_svg_to_pes(svg_to_convert, output_dir)

        # 6. Métadonnées + score
        metadata = extract_pes_metadata(
            pes_path,
            source_svg_path=svg_to_convert,
            n_colors_requested=n_colors,
        )

        return {
            'score': metadata.get('quality_score', 0),
            'score_details': metadata.get('quality_details', {}),
            'metadata': {k: v for k, v in metadata.items() if k not in ('quality_details',)},
        }

    finally:
        for p in tmp_pngs:
            if p and p.exists():
                p.unlink(missing_ok=True)
        if scaled_path and scaled_path.exists():
            scaled_path.unlink(missing_ok=True)


def _run_svg_pipeline(
    input_path: Path,
    target_width_mm: int,
    tmp_dir: Path,
) -> dict[str, Any]:
    """Pipeline SVG direct → PES (copie pour ne pas modifier l'original)."""
    output_dir = tmp_dir / 'output'
    output_dir.mkdir()

    # Copier pour travailler in-place sans toucher au fichier source
    svg_work = tmp_dir / input_path.name
    shutil.copy2(input_path, svg_work)

    scaled_path: Path | None = None
    try:
        svg_to_convert, scaled_path = _apply_svg_postprocess(
            svg_work,
            target_width_mm=target_width_mm,
            remove_bg=False,  # pas de suppression fond pour SVG direct
            n_colors_requested=None,
        )

        pes_path = convert_svg_to_pes(svg_to_convert, output_dir)

        metadata = extract_pes_metadata(
            pes_path,
            source_svg_path=svg_to_convert,
            n_colors_requested=None,  # SVG direct : pas de n_colors_requested
        )

        return {
            'score': metadata.get('quality_score', 0),
            'score_details': metadata.get('quality_details', {}),
            'metadata': {k: v for k, v in metadata.items() if k not in ('quality_details',)},
        }

    finally:
        if scaled_path and scaled_path.exists():
            scaled_path.unlink(missing_ok=True)


def _run_pdf_pipeline(
    input_path: Path,
    n_colors: int,
    remove_bg: bool,
    target_width_mm: int,
    tmp_dir: Path,
) -> dict[str, Any]:
    """Pipeline PDF → (vectoriel direct SVG) ou (raster → PNG → SVG) → PES."""
    output_dir = tmp_dir / 'output'
    output_dir.mkdir()

    tmp_svg = tmp_dir / 'extracted.svg'
    scaled_path: Path | None = None
    tmp_pngs: list[Path] = []

    try:
        extract_vector_svg_from_pdf(input_path, tmp_svg)

        if is_vector_pdf_svg(tmp_svg):
            # PDF vectoriel → pipeline SVG direct
            postprocess_vector_svg(tmp_svg)
            svg_work = tmp_svg

            svg_to_convert, scaled_path = _apply_svg_postprocess(
                svg_work,
                target_width_mm=target_width_mm,
                remove_bg=False,
                n_colors_requested=n_colors,
            )

            pes_path = convert_svg_to_pes(svg_to_convert, output_dir)

            # PDF vectoriel : n_colors_requested = n_colors (cohérent avec tasks.py ligne 208)
            metadata = extract_pes_metadata(
                pes_path,
                source_svg_path=svg_to_convert,
                n_colors_requested=n_colors,
            )

        else:
            # PDF scanné → pipeline raster
            if tmp_svg.exists():
                tmp_svg.unlink()

            png_path = convert_pdf_to_png(input_path)
            tmp_pngs.append(png_path)

            validate_png(png_path)
            processed = preprocess_image(png_path)
            tmp_pngs.append(processed)

            if remove_bg:
                processed = remove_background(processed)
                tmp_pngs.append(processed)

            svg_path = vectorize_to_svg(processed, n_colors=n_colors)
            tmp_pngs.append(svg_path)

            svg_to_convert, scaled_path = _apply_svg_postprocess(
                svg_path,
                target_width_mm=target_width_mm,
                remove_bg=True,
                n_colors_requested=n_colors,
            )

            pes_path = convert_svg_to_pes(svg_to_convert, output_dir)

            metadata = extract_pes_metadata(
                pes_path,
                source_svg_path=svg_to_convert,
                n_colors_requested=n_colors,
            )

        return {
            'score': metadata.get('quality_score', 0),
            'score_details': metadata.get('quality_details', {}),
            'metadata': {k: v for k, v in metadata.items() if k not in ('quality_details',)},
        }

    finally:
        for p in tmp_pngs:
            if p and p.exists():
                p.unlink(missing_ok=True)
        if scaled_path and scaled_path.exists():
            scaled_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Runner principal
# ---------------------------------------------------------------------------

def run_test(test: dict[str, Any]) -> dict[str, Any]:
    """Lance un test et retourne le résultat structuré."""
    test_id = test['test_id']
    file_rel = test['file']
    fmt = test['format']
    n_colors = test.get('n_colors') or 6
    remove_bg = test.get('remove_bg', False)
    target_width_mm = test.get('target_width_mm', 80)

    input_path = TESTS_DIR / file_rel
    if not input_path.exists():
        return {
            'test_id': test_id,
            'file': str(file_rel),
            'format': fmt,
            'params': {'n_colors': n_colors, 'remove_bg': remove_bg, 'target_width_mm': target_width_mm},
            'score': 0,
            'score_details': {},
            'error': f'Fichier introuvable : {input_path}',
            'duration_s': 0.0,
        }

    print(f'  [{test_id}] {file_rel}... ', end='', flush=True)
    t0 = time.time()

    try:
        with tempfile.TemporaryDirectory(prefix=f'benchmark_{test_id}_') as tmp_str:
            tmp_dir = Path(tmp_str)

            if fmt == 'svg':
                result = _run_svg_pipeline(input_path, target_width_mm, tmp_dir)
            elif fmt == 'pdf':
                result = _run_pdf_pipeline(input_path, n_colors, remove_bg, target_width_mm, tmp_dir)
            else:  # png / jpeg / webp
                result = _run_raster_pipeline(
                    input_path, fmt, n_colors, remove_bg, target_width_mm, tmp_dir
                )

        duration = round(time.time() - t0, 1)
        score = result['score']
        label = result['metadata'].get('quality_label', '?')
        print(f'{score}/100 ({label}) [{duration}s]')

        return {
            'test_id': test_id,
            'file': str(file_rel),
            'format': fmt,
            'params': {'n_colors': n_colors, 'remove_bg': remove_bg, 'target_width_mm': target_width_mm},
            'score': score,
            'score_details': result['score_details'],
            'metadata': result['metadata'],
            'error': None,
            'duration_s': duration,
        }

    except Exception as exc:
        duration = round(time.time() - t0, 1)
        error_msg = f'{type(exc).__name__}: {exc}'
        print(f'ERREUR [{duration}s] → {error_msg}')

        return {
            'test_id': test_id,
            'file': str(file_rel),
            'format': fmt,
            'params': {'n_colors': n_colors, 'remove_bg': remove_bg, 'target_width_mm': target_width_mm},
            'score': 0,
            'score_details': {},
            'error': error_msg,
            'duration_s': duration,
        }


def print_summary(results: list[dict[str, Any]]) -> None:
    """Affiche le tableau récapitulatif et le score moyen."""
    print('\n' + '═' * 80)
    print('RÉSULTATS DU BENCHMARK')
    print('═' * 80)
    print(f'{"ID":<5} {"Format":<7} {"Score":>6}  {"Label":<15} {"Erreur":<40}')
    print('─' * 80)

    scores = []
    for r in results:
        score_str = f'{r["score"]}/100' if r['error'] is None else '  —'
        label = r.get('metadata', {}).get('quality_label', '—') if r['error'] is None else 'ERREUR'
        error_short = (r['error'] or '')[:38] if r['error'] else ''
        print(f'{r["test_id"]:<5} {r["format"]:<7} {score_str:>6}  {label:<15} {error_short:<40}')
        if r['error'] is None:
            scores.append(r['score'])

    print('─' * 80)
    if scores:
        avg = sum(scores) / len(scores)
        ceiling = 67.5  # ceiling théorique 65-70
        toward_ceiling = max(0, (avg - 0) / ceiling * 100)
        print(f'\n  Score moyen   : {avg:.1f}/100 ({len(scores)}/{len(results)} tests OK)')
        print(f'  Ceiling       : {ceiling}/100 (limite auto-digitizing sans retouche)')
        print(f'  Vers ceiling  : {toward_ceiling:.0f}% du chemin parcouru')
    else:
        print('\n  Aucun test réussi.')


def main() -> None:
    parser = argparse.ArgumentParser(description='Benchmark pipeline StitchFlow')
    parser.add_argument(
        '--tests', default=None,
        help='IDs de tests à lancer (ex : T01,T08). Par défaut : tous.'
    )
    parser.add_argument(
        '--output', default=None,
        help='Chemin JSON de sortie. Par défaut : tests/benchmark_results_TIMESTAMP.json'
    )
    parser.add_argument(
        '--quiet', action='store_true',
        help='Supprime les logs Django/services pendant le benchmark'
    )
    args = parser.parse_args()

    if args.quiet:
        logging.disable(logging.WARNING)

    # Filtre optionnel des tests
    tests_to_run = TESTS
    if args.tests:
        ids = {t.strip().upper() for t in args.tests.split(',')}
        tests_to_run = [t for t in TESTS if t['test_id'] in ids]
        if not tests_to_run:
            print(f'Aucun test trouvé pour : {args.tests}')
            sys.exit(1)

    print(f'\nBENCHMARK STITCHFLOW — {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'Lancement de {len(tests_to_run)} test(s)...\n')

    results = []
    for test in tests_to_run:
        result = run_test(test)
        results.append(result)

    print_summary(results)

    # Sauvegarde JSON
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = Path(args.output) if args.output else (ROOT / 'tests' / f'benchmark_results_{ts}.json')
    output_data = {
        'run_at': datetime.now().isoformat(),
        'n_tests': len(results),
        'n_ok': sum(1 for r in results if r['error'] is None),
        'score_mean': round(
            sum(r['score'] for r in results if r['error'] is None)
            / max(1, sum(1 for r in results if r['error'] is None)),
            1,
        ),
        'results': results,
    }
    output_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'\n  Résultats JSON : {output_path}')


if __name__ == '__main__':
    main()
