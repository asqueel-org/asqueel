"""Check docs/design/112-legacy-inventory.md against the format and the two code bases.

Usage: python check_inventory.py --areas 1-4   (or 1-8)
Run from the asqueel repository root. The GenroPy checkout is read from
$GENROPY_REPO (default ~/Sviluppo/Genropy/genropy) at the fixed reference.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

INVENTORY = Path('docs/design/112-legacy-inventory.md')
LEGACY_REF = '95da66ee64b0c789dbb6b35254011d83ce1911c5'
AREAS = {1: 'Modello', 2: 'Query', 3: 'Formule', 4: 'Relazioni',
         5: 'Scritture', 6: 'Transazioni', 7: 'Migrazione', 8: 'Dialetti'}
HEADER = ['ID', 'Funzione', 'Legacy', 'Asqueel', 'Stato', 'Motivazione', 'Alternative']
STATES = {'presente', 'diverso', 'mancante', 'nuovo'}
LEGACY_RE = re.compile(r'gnrpy/[\w/.-]+\.py:\d+')
ASQUEEL_RE = re.compile(r'(?:src|tests|docs)/[\w/.-]+:\d+')
SOURCE_RE = re.compile(r'docs/[\w/.-]+|#\d+|decisione utente \d{4}-\d{2}-\d{2}')
ISSUE_RE = re.compile(r'#\d+|nessuna issue')
MIN_ROWS = 5


def legacy_lines(path, cache={}):
    if path not in cache:
        repo = os.path.expanduser(os.environ.get('GENROPY_REPO', '~/Sviluppo/Genropy/genropy'))
        result = subprocess.run(['git', '-C', repo, 'show', f'{LEGACY_REF}:{path}'],
                                capture_output=True, text=True)
        cache[path] = None if result.returncode else result.stdout.count('\n') + 1
    return cache[path]


def asqueel_lines(path):
    file = Path(path)
    return file.read_text().count('\n') + 1 if file.is_file() else None


def check_refs(errors, row_id, text, pattern, count_lines):
    for ref in pattern.findall(text):
        path, line = ref.rsplit(':', 1)
        total = count_lines(path)
        if total is None:
            errors.append(f'{row_id}: {path} does not exist')
        elif int(line) > total:
            errors.append(f'{row_id}: {ref} beyond the end of the file ({total} lines)')


def parse(text):
    areas, current = {}, None
    for line in text.splitlines():
        heading = re.match(r'^## (\d) (\w+)\s*$', line)
        if heading:
            current = int(heading.group(1))
            areas[current] = {'title': heading.group(2), 'header': None, 'rows': []}
        elif current and line.startswith('|') and not re.match(r'^\|[\s|:-]+\|$', line):
            cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
            if areas[current]['header'] is None:
                areas[current]['header'] = cells
            else:
                areas[current]['rows'].append(cells)
    return areas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--areas', required=True, help='range like 1-4 or 1-8')
    first, last = (int(n) for n in parser.parse_args().areas.split('-'))
    if not INVENTORY.is_file():
        sys.exit(f'{INVENTORY} missing')
    areas = parse(INVENTORY.read_text())
    errors, seen, total = [], set(), 0
    for number in range(first, last + 1):
        area = areas.get(number)
        if area is None or area['title'] != AREAS[number]:
            errors.append(f'area heading "## {number} {AREAS[number]}" missing')
            continue
        if area['header'] != HEADER:
            errors.append(f'area {number}: header must be {" | ".join(HEADER)}')
            continue
        if len(area['rows']) < MIN_ROWS:
            errors.append(f'area {number}: {len(area["rows"])} rows, at least {MIN_ROWS} required')
        for cells in area['rows']:
            if len(cells) != len(HEADER):
                errors.append(f'area {number}: row with {len(cells)} cells: {cells[:2]}')
                continue
            row_id, feature, legacy, asqueel, state, reason, alternatives = cells
            total += 1
            if not re.fullmatch(rf'A{number}\.\d+', row_id) or row_id in seen:
                errors.append(f'{row_id}: id must be A{number}.<n> and unique')
            seen.add(row_id)
            if not feature:
                errors.append(f'{row_id}: Funzione empty')
            if state not in STATES:
                errors.append(f'{row_id}: Stato "{state}" not in {sorted(STATES)}')
                continue
            if state != 'nuovo' and not LEGACY_RE.search(legacy):
                errors.append(f'{row_id}: Legacy needs a gnrpy/<path>.py:<line> reference')
            if state != 'mancante' and not ASQUEEL_RE.search(asqueel):
                errors.append(f'{row_id}: Asqueel needs a src|tests|docs/<path>:<line> reference')
            if state in ('diverso', 'nuovo') and not SOURCE_RE.search(reason):
                errors.append(f'{row_id}: Motivazione needs a source (docs/..., #n, decisione utente YYYY-MM-DD)')
            if state == 'mancante':
                if not ISSUE_RE.search(reason + ' ' + asqueel):
                    errors.append(f'{row_id}: mancante needs #<issue> or "nessuna issue"')
                if not ('(a)' in alternatives and '(b)' in alternatives):
                    errors.append(f'{row_id}: mancante needs at least alternatives (a) and (b)')
            check_refs(errors, row_id, legacy, LEGACY_RE, legacy_lines)
            check_refs(errors, row_id, asqueel + ' ' + reason, ASQUEEL_RE, asqueel_lines)
    for error in errors:
        print(error)
    print(f'{total} rows checked in areas {first}-{last}, {len(errors)} errors')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
