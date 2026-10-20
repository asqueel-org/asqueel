"""Check docs/guide/legacy-features.md ("Differences from GenroPy") against the inventory.

Usage: python check_chapter.py
Run from the asqueel repository root, after Phase 1 (the inventory is the source).
"""
import importlib.util
import re
import sys
from pathlib import Path

CHAPTER = Path('docs/guide/legacy-features.md')
CSS = Path('docs/_static/differences.css')
CONF = Path('docs/conf.py')
H2 = ['Model', 'Query', 'Read-Write', 'Adapters', 'To implement', 'Migration',
      'Low-level and high-level API', 'Proposals']
BLOCKS = ['Model', 'Query', 'Read-Write', 'Adapters']
BRANCHES = ['Missing', 'Different', 'New', 'Same']
BRANCH_OF = {'uguale': 'Same', 'diverso': 'Different', 'nuovo': 'New',
             'mancante-temporanea': 'Missing', 'mancante-eliminata': 'Missing',
             'mancante-sostituita': 'Missing'}
LABEL_OF = {'mancante-temporanea': 'temporary', 'mancante-eliminata': 'removed',
            'mancante-sostituita': 'replaced'}
TWO_SIDED = {'diverso', 'mancante-sostituita'}
MIGRATION_TERMS = ['asqueel-migration', 'project_tree', 'migration_plan', 'migrate(']
PROPOSAL_TERMS = ['sqlglot', '.sql(', 'capabilit', 'async']


def inventory_rows():
    path = Path(__file__).resolve().parent.parent / 'phase-1' / 'check_inventory.py'
    spec = importlib.util.spec_from_file_location('check_inventory', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    areas, _sections = module.parse(module.INVENTORY.read_text())
    rows = {}
    for area in areas.values():
        for cells in area['rows']:
            rows[cells[0]] = {'state': cells[4], 'block': cells[5]}
    return rows


def parse(text):
    """Return H2 order, H3 order per H2, cards and same-items with their place."""
    h2, h3, cards, same = [], {}, {}, {}
    current_h2 = current_h3 = None
    pending_label = None
    card = None
    for line in text.splitlines():
        label = re.match(r'^\((a\d-\d+)\)=\s*$', line)
        heading = re.match(r'^(#{2,4}) (.+?)\s*$', line)
        if label:
            pending_label = label.group(1)
            continue
        if heading:
            level, title = len(heading.group(1)), heading.group(2)
            if level == 2:
                current_h2, current_h3, card = title, None, None
                h2.append(title)
                h3[title] = []
            elif level == 3:
                current_h3, card = title, None
                h3.setdefault(current_h2, []).append(title)
            else:
                card = None
                if pending_label:
                    row_id = 'A' + pending_label[1:].replace('-', '.')
                    card = {'h2': current_h2, 'h3': current_h3, 'title': title, 'body': []}
                    cards.setdefault(row_id, []).append(card)
            pending_label = None
            continue
        pending_label = None
        if card is not None:
            card['body'].append(line)
            continue
        bullet = re.match(r'^- .*\((A\d\.\d+)\)\s*$', line)
        if bullet:
            same.setdefault(bullet.group(1), []).append({'h2': current_h2, 'h3': current_h3})
    return h2, h3, cards, same


def main():
    if not CHAPTER.is_file():
        sys.exit(f'{CHAPTER} missing')
    text = CHAPTER.read_text()
    rows = inventory_rows()
    h2, h3, cards, same = parse(text)
    errors = []
    if not text.startswith('# Differences from GenroPy\n'):
        errors.append('first line must be "# Differences from GenroPy"')
    if h2 != H2:
        errors.append(f'## headings must be exactly {H2}, found {h2}')
    for block in BLOCKS:
        if h3.get(block) != BRANCHES:
            errors.append(f'## {block}: ### headings must be exactly {BRANCHES}, found {h3.get(block)}')
    pending = [b for b in BLOCKS if any(r['state'] == 'da-implementare' and r['block'] == b
                                        for r in rows.values())]
    if h3.get('To implement') != pending:
        errors.append(f'## To implement: ### headings must be exactly {pending}, '
                      f'found {h3.get("To implement")}')
    for row_id, row in rows.items():
        state, block = row['state'], row['block']
        places = cards.get(row_id, []) + same.get(row_id, [])
        if block == 'Migration':
            if places or re.search(rf'\b{re.escape(row_id)}\b', text):
                errors.append(f'{row_id}: Migration rows are not carded or cited')
            continue
        if len(places) != 1:
            errors.append(f'{row_id}: must appear exactly once, found {len(places)}')
            continue
        place = places[0]
        if state == 'da-implementare':
            where = ('To implement', block)
        else:
            where = (block, BRANCH_OF[state])
        if (place['h2'], place['h3']) != where:
            errors.append(f'{row_id}: under {place["h2"]} / {place["h3"]}, expected {where[0]} / {where[1]}')
        if state == 'uguale':
            if row_id in cards:
                errors.append(f'{row_id}: Same items are bullets ending with ({row_id}), not cards')
            continue
        if row_id not in cards:
            errors.append(f'{row_id}: needs a card: "(a{row_id[1:].replace(".", "-")})=" then a #### heading')
            continue
        card = cards[row_id][0]
        labels = re.findall(r'class="asq-label asq-label-(\w+)"', card['title'])
        if state in LABEL_OF:
            if labels != [LABEL_OF[state]]:
                errors.append(f'{row_id}: heading needs exactly one asq-label-{LABEL_OF[state]}, found {labels}')
        elif labels:
            errors.append(f'{row_id}: only Missing cards carry a label, found {labels}')
        body = '\n'.join(card['body'])
        if state in TWO_SIDED and not ('In GenroPy' in body and 'In asqueel' in body):
            errors.append(f'{row_id}: card needs "In GenroPy" above and "In asqueel" below')
        if '<details>' not in body:
            errors.append(f'{row_id}: card needs a closed <details> block with the files')
    unknown = (set(cards) | set(same)) - set(rows)
    for row_id in sorted(unknown):
        errors.append(f'{row_id}: cited in the chapter but not a row of the inventory')
    sections = re.split(r'^## ', text, flags=re.M)
    by_title = {part.split('\n', 1)[0].strip(): part for part in sections[1:]}
    for term in MIGRATION_TERMS:
        if term not in by_title.get('Migration', ''):
            errors.append(f'## Migration must name {term}')
    for term in PROPOSAL_TERMS:
        if term not in by_title.get('Proposals', ''):
            errors.append(f'## Proposals must name {term}')
    if not CSS.is_file():
        errors.append(f'{CSS} missing')
    if 'differences.css' not in CONF.read_text():
        errors.append('docs/conf.py must list differences.css in html_css_files')
    for error in errors:
        print(error)
    print(f'{len(rows)} inventory rows checked, {len(errors)} errors')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
