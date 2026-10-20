"""Check docs/design/112-legacy-inventory.md: format, blocks, states, sources, summary.

Usage: python check_inventory.py
Run from the asqueel repository root. The GenroPy checkout is read from
$GENROPY_REPO (default ~/Sviluppo/Genropy/genropy) at the fixed reference.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

INVENTORY = Path('docs/design/112-legacy-inventory.md')
LEGACY_REF = '95da66ee64b0c789dbb6b35254011d83ce1911c5'
OLD_ASQUEEL_REF = '4361e769a53148c83a527fa1afa02dd2ac796668'
AREAS = {1: 'Modello', 2: 'Query', 3: 'Formule', 4: 'Relazioni',
         5: 'Scritture', 6: 'Transazioni', 7: 'Migrazione', 8: 'Adapter'}
ORIGINAL_ROWS = {1: 27, 2: 26, 3: 20, 4: 21, 5: 30, 6: 29, 7: 29, 8: 23}
HEADER = ['ID', 'Funzione', 'Legacy', 'Asqueel', 'Stato', 'Blocco', 'Motivazione', 'Alternative']
STATES = ['uguale', 'diverso', 'nuovo', 'mancante-temporanea', 'mancante-eliminata',
          'mancante-sostituita', 'da-implementare']
BLOCKS = ['Model', 'Query', 'Read-Write', 'Adapters', 'Migration']
WITHOUT_ASQUEEL = {'mancante-temporanea', 'mancante-eliminata', 'da-implementare'}
LEGACY_RE = re.compile(r'gnrpy/[\w/.-]+\.py:\d+')
ASQUEEL_RE = re.compile(r'(?:src|tests|docs)/[\w/.-]+:\d+')
SOURCE_RE = re.compile(r'docs/[\w/.-]+|#\d+|decisione utente \d{4}-\d{2}-\d{2}|nessuna issue')


def expected_blocks(area, number):
    if area in (1, 4):
        return {'Model'}
    if area == 2:
        return {'Query'}
    if area == 3:
        if number <= 15:
            return {'Model'}
        if number <= 20:
            return {'Query'}
        return {'Model', 'Query'}
    if area in (5, 6):
        return {'Read-Write'}
    if area == 7:
        return {'Migration'}
    return {'Adapters'}


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
    areas, sections, current, section = {}, {}, None, None
    for line in text.splitlines():
        heading = re.match(r'^## (\d) (\w+)\s*$', line)
        other = re.match(r'^## (.+?)\s*$', line)
        if heading:
            current, section = int(heading.group(1)), None
            areas[current] = {'title': heading.group(2), 'header': None, 'rows': []}
        elif other:
            current, section = None, other.group(1)
            sections[section] = []
        elif current and line.startswith('|') and not re.match(r'^\|[\s|:-]+\|$', line):
            cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
            if areas[current]['header'] is None:
                areas[current]['header'] = cells
            else:
                areas[current]['rows'].append(cells)
        elif section is not None:
            sections[section].append(line)
    return areas, sections


def check_sources(errors, lines):
    commits = re.findall(r'\b[0-9a-f]{40}\b', '\n'.join(lines))
    fresh = [c for c in commits if c not in (LEGACY_REF, OLD_ASQUEEL_REF)]
    if not fresh:
        errors.append('## Fonti must cite the asqueel commit the rows were verified at (40 hex)')
    for commit in fresh:
        result = subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'HEAD'])
        if result.returncode:
            errors.append(f'## Fonti: {commit} is not an ancestor of HEAD')
    if OLD_ASQUEEL_REF in '\n'.join(lines):
        errors.append('## Fonti still cites the old asqueel commit 4361e769')


def check_removed(errors, lines, present):
    removed = {}
    for line in lines:
        match = re.match(r'^- (A\d\.\d+): (.+)$', line)
        if match:
            removed[match.group(1)] = match.group(2)
    for area, count in ORIGINAL_ROWS.items():
        for number in range(1, count + 1):
            row_id = f'A{area}.{number}'
            if row_id not in present and row_id not in removed:
                errors.append(f'{row_id}: original row missing and not listed in ## Righe tolte')
            if row_id in present and row_id in removed:
                errors.append(f'{row_id}: both a row and listed in ## Righe tolte')
    for row_id in removed:
        area, number = (int(n) for n in row_id[1:].split('.'))
        if number > ORIGINAL_ROWS[area]:
            errors.append(f'{row_id}: ## Righe tolte lists only original rows')


def check_summary(errors, lines, counts):
    expected = {}
    for block in BLOCKS + ['Totale']:
        per_state = counts.get(block, {})
        parts = ', '.join(f'{per_state.get(state, 0)} {state}' for state in STATES)
        expected[block] = f'- {block}: {parts}; {sum(per_state.values())} righe.'
    found = [line for line in lines if line.startswith('- ')]
    if found != list(expected.values()):
        errors.append('## Riepilogo must be exactly:\n' + '\n'.join(expected.values()))


def main():
    if not INVENTORY.is_file():
        sys.exit(f'{INVENTORY} missing')
    areas, sections = parse(INVENTORY.read_text())
    errors, seen, counts = [], set(), {'Totale': {}}
    for name in ('Fonti', 'Righe tolte', 'Riepilogo'):
        if name not in sections:
            errors.append(f'section "## {name}" missing')
    check_sources(errors, sections.get('Fonti', []))
    for area_number, title in AREAS.items():
        area = areas.get(area_number)
        if area is None or area['title'] != title:
            errors.append(f'area heading "## {area_number} {title}" missing')
            continue
        if area['header'] != HEADER:
            errors.append(f'area {area_number}: header must be {" | ".join(HEADER)}')
            continue
        for cells in area['rows']:
            if len(cells) != len(HEADER):
                errors.append(f'area {area_number}: row with {len(cells)} cells: {cells[:2]}')
                continue
            row_id, feature, legacy, asqueel, state, block, reason, _alternatives = cells
            match = re.fullmatch(rf'A{area_number}\.(\d+)', row_id)
            if not match or row_id in seen:
                errors.append(f'{row_id}: id must be A{area_number}.<n> and unique')
                continue
            seen.add(row_id)
            if not feature:
                errors.append(f'{row_id}: Funzione empty')
            if state not in STATES:
                errors.append(f'{row_id}: Stato "{state}" not in {STATES}')
                continue
            if block not in expected_blocks(area_number, int(match.group(1))):
                errors.append(f'{row_id}: Blocco "{block}" must be one of '
                              f'{sorted(expected_blocks(area_number, int(match.group(1))))}')
                continue
            if state != 'nuovo' and not LEGACY_RE.search(legacy):
                errors.append(f'{row_id}: Legacy needs a gnrpy/<path>.py:<line> reference')
            if state not in WITHOUT_ASQUEEL and not ASQUEEL_RE.search(asqueel):
                errors.append(f'{row_id}: Asqueel needs a src|tests|docs/<path>:<line> reference')
            if state != 'uguale' and not SOURCE_RE.search(reason):
                errors.append(f'{row_id}: Motivazione needs a source '
                              '(docs/..., #n, nessuna issue, decisione utente YYYY-MM-DD)')
            check_refs(errors, row_id, legacy, LEGACY_RE, legacy_lines)
            check_refs(errors, row_id, asqueel + ' ' + reason, ASQUEEL_RE, asqueel_lines)
            for key in (block, 'Totale'):
                counts.setdefault(key, {})
                counts[key][state] = counts[key].get(state, 0) + 1
    check_removed(errors, sections.get('Righe tolte', []), seen)
    check_summary(errors, sections.get('Riepilogo', []), counts)
    for error in errors:
        print(error)
    print(f'{len(seen)} rows checked, {len(errors)} errors')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
