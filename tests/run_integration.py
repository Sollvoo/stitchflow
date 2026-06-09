#!/usr/bin/env python3
"""
Tests d'intégration StitchFlow — Phase 6d.

Lance de vraies conversions via Django + Celery (HTTP) et compare
les scores qualité obtenus aux seuils attendus par catégorie.

Usage:
    python tests/run_integration.py [--base-url URL] [--output FILE] [--timeout SEC]

Prérequis:
    - Django tournant sur BASE_URL (défaut: http://localhost:8001)
    - Worker Celery actif
    - Fixtures générées: python tests/generate_fixtures.py
"""
import argparse
import http.cookiejar
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / 'fixtures'

# Scores minimaux attendus par fixture (extrait du README.md)
EXPECTED: dict[str, dict] = {
    # logos/
    'logos/logo-simple-3couleurs.svg': {
        'min_score': 85, 'n_colors': 3, 'target_width_mm': 100,
    },
    'logos/logo-complexe-7couleurs-texte.svg': {
        'min_score': 75, 'n_colors': 7, 'target_width_mm': 100,
    },
    'logos/logo-fond-blanc.png': {
        'min_score': 70, 'n_colors': 4, 'target_width_mm': 100, 'remove_background': True,
    },
    'logos/logo-fond-transparent.png': {
        'min_score': 65, 'n_colors': 4, 'target_width_mm': 100, 'remove_background': True,
    },
    # ecusson/
    'ecusson/ecusson-club-6couleurs.png': {
        'min_score': 70, 'n_colors': 6, 'target_width_mm': 100,
    },
    'ecusson/patch-sportif-texte-graphique.png': {
        'min_score': 65, 'n_colors': 8, 'target_width_mm': 100,
    },
    'ecusson/badge-contours-fins.svg': {
        'min_score': 55, 'n_colors': 5, 'target_width_mm': 100,
    },
    # texte/
    'texte/monogramme-initiales.svg': {
        'min_score': 80, 'n_colors': 3, 'target_width_mm': 80,
    },
    'texte/texte-multicolore-8couleurs.svg': {
        'min_score': 65, 'n_colors': 8, 'target_width_mm': 80,
    },
    'texte/texte-contours-fins.svg': {
        'min_score': 50, 'n_colors': 4, 'target_width_mm': 80,
    },
    # geometrique/
    'geometrique/motif-repetitif-losanges.svg': {
        'min_score': 70, 'n_colors': 4, 'target_width_mm': 100,
    },
    'geometrique/cercles-concentriques-5couleurs.png': {
        'min_score': 65, 'n_colors': 5, 'target_width_mm': 100,
    },
    'geometrique/abstrait-6couleurs.svg': {
        'min_score': 60, 'n_colors': 6, 'target_width_mm': 100,
    },
    # pdf/
    'pdf/logo-vectoriel.pdf': {
        'min_score': 75, 'n_colors': 4, 'target_width_mm': 100,
    },
    'pdf/texte-vectoriel.pdf': {
        'min_score': 70, 'n_colors': 3, 'target_width_mm': 100,
    },
    'pdf/simule-scanne.pdf': {
        'min_score': 50, 'n_colors': 4, 'target_width_mm': 100,
    },
}

CATEGORY_ORDER = ['logos', 'ecusson', 'texte', 'geometrique', 'pdf']


def _build_opener() -> urllib.request.OpenerDirector:
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPRedirectHandler(),
    )


def _get_csrf_token(opener: urllib.request.OpenerDirector, base_url: str) -> str:
    req = urllib.request.Request(f'{base_url}/conversions/')
    with opener.open(req, timeout=10) as resp:
        for cookie in opener.handlers[0].cookiejar:  # type: ignore[attr-defined]
            if cookie.name == 'csrftoken':
                return cookie.value
    raise RuntimeError('Cookie csrftoken introuvable après GET /conversions/')


def _encode_multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    for name, (filename, data, content_type) in files.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n'.encode()
            + data
            + b'\r\n'
        )
    parts.append(f'--{boundary}--\r\n'.encode())
    body = b''.join(parts)
    return body, f'multipart/form-data; boundary={boundary}'


def _post_file(opener: urllib.request.OpenerDirector, base_url: str, csrf_token: str,
               fixture_path: Path, params: dict) -> str:
    fields = {'csrfmiddlewaretoken': csrf_token}
    if 'n_colors' in params:
        fields['n_colors'] = str(params['n_colors'])
    if 'target_width_mm' in params:
        fields['target_width_mm'] = str(params['target_width_mm'])
    if params.get('remove_background'):
        fields['remove_background'] = 'on'

    mime = mimetypes.guess_type(fixture_path.name)[0] or 'application/octet-stream'
    body, content_type = _encode_multipart(
        fields,
        {'original_file': (fixture_path.name, fixture_path.read_bytes(), mime)},
    )

    req = urllib.request.Request(
        f'{base_url}/conversions/',
        data=body,
        headers={
            'Content-Type': content_type,
            'X-CSRFToken': csrf_token,
        },
        method='POST',
    )
    with opener.open(req, timeout=30) as resp:
        job_url = resp.url
        if '/conversions/' not in job_url:
            raise RuntimeError(f'Redirect inattendu : {job_url}')
        parts = [p for p in job_url.rstrip('/').split('/') if p]
        return parts[-1]


def _poll_status(opener: urllib.request.OpenerDirector, base_url: str, job_id: str,
                 timeout_s: int) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        url = f'{base_url}/conversions/{job_id}/api/status/'
        with opener.open(url, timeout=10) as resp:
            data = json.loads(resp.read())
        if data['status'] in ('completed', 'failed'):
            return data
        time.sleep(3)
    return {'status': 'timeout', 'quality_score': None, 'error_message': 'timeout'}


def _category(fixture_key: str) -> str:
    return fixture_key.split('/')[0]


def run(base_url: str, timeout_s: int) -> list[dict]:
    results = []
    opener = _build_opener()

    print(f'Connexion à {base_url} …', flush=True)
    try:
        csrf_token = _get_csrf_token(opener, base_url)
    except Exception as exc:
        print(f'ERREUR : impossible de joindre Django — {exc}', file=sys.stderr)
        sys.exit(1)

    for fixture_key, params in EXPECTED.items():
        fixture_path = FIXTURES_DIR / fixture_key
        if not fixture_path.exists():
            results.append({
                'fixture': fixture_key,
                'category': _category(fixture_key),
                'expected_min': params['min_score'],
                'actual_score': None,
                'status': 'skip',
                'error': 'fichier absent (générer avec generate_fixtures.py)',
                'duration_s': 0,
            })
            print(f'  SKIP {fixture_key} (fichier absent)', flush=True)
            continue

        t0 = time.monotonic()
        try:
            job_id = _post_file(opener, base_url, csrf_token, fixture_path, params)
            data = _poll_status(opener, base_url, job_id, timeout_s)
        except urllib.error.URLError as exc:
            results.append({
                'fixture': fixture_key,
                'category': _category(fixture_key),
                'expected_min': params['min_score'],
                'actual_score': None,
                'status': 'error',
                'error': str(exc),
                'duration_s': round(time.monotonic() - t0, 1),
            })
            print(f'  ERROR {fixture_key}: {exc}', flush=True)
            continue

        duration = round(time.monotonic() - t0, 1)
        score = data.get('quality_score')
        expected_min = params['min_score']

        if data['status'] == 'failed':
            test_status = 'error'
        elif data['status'] == 'timeout':
            test_status = 'timeout'
        elif score is None:
            test_status = 'error'
        elif score >= expected_min:
            test_status = 'pass'
        else:
            test_status = 'fail'

        result = {
            'fixture': fixture_key,
            'category': _category(fixture_key),
            'expected_min': expected_min,
            'actual_score': score,
            'status': test_status,
            'duration_s': duration,
        }
        if data.get('error_message'):
            result['error'] = data['error_message']

        results.append(result)
        icon = {'pass': '✓', 'fail': '✗', 'error': '!', 'timeout': 'T'}.get(test_status, '?')
        score_str = f'{score}/100' if score is not None else 'N/A'
        print(f'  {icon} {fixture_key}: score={score_str} (min={expected_min}) [{duration_s}s]'
              .replace('[', '[').replace(']', ']').replace('duration_s', str(duration)),
              flush=True)

    return results


def _print_summary(results: list[dict]) -> None:
    print('\n' + '=' * 60)
    print('RÉSUMÉ PAR CATÉGORIE')
    print('=' * 60)

    by_category: dict[str, list[dict]] = {}
    for r in results:
        by_category.setdefault(r['category'], []).append(r)

    total_pass = total_fail = total_skip = 0
    for cat in CATEGORY_ORDER:
        items = by_category.get(cat, [])
        if not items:
            continue
        passed = [r for r in items if r['status'] == 'pass']
        failed = [r for r in items if r['status'] == 'fail']
        errors = [r for r in items if r['status'] in ('error', 'timeout', 'skip')]
        scores = [r['actual_score'] for r in items if isinstance(r.get('actual_score'), (int, float))]
        avg = round(sum(scores) / len(scores), 1) if scores else None
        total_pass += len(passed)
        total_fail += len(failed)
        total_skip += len(errors)
        print(f'  {cat:15s}  pass={len(passed)}/{len(items)}  avg_score={avg}  fail={len(failed)}  err={len(errors)}')

    all_run = total_pass + total_fail
    print(f'\n  TOTAL  pass={total_pass}/{all_run}  skip/err={total_skip}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Tests intégration StitchFlow Phase 6d')
    parser.add_argument('--base-url', default='http://localhost:8001', help='URL base Django')
    parser.add_argument('--output', default=None, help='Fichier JSON de sortie (optionnel)')
    parser.add_argument('--timeout', type=int, default=180, help='Timeout par fixture (secondes)')
    args = parser.parse_args()

    print(f'StitchFlow — Tests intégration Phase 6d')
    print(f'Base URL : {args.base_url} | timeout : {args.timeout}s | fixtures : {FIXTURES_DIR}')
    print()

    results = run(args.base_url, args.timeout)
    _print_summary(results)

    report = {
        'base_url': args.base_url,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'results': results,
    }

    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f'\nRapport JSON écrit dans {args.output}')
    else:
        print('\n' + json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
