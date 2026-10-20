"""Check docs/review/differenze-asqueel-genropy-it.html against the inventory.

Usage: python check_page.py
Run from the asqueel repository root, after Phase 1 (the inventory is the source).
"""
import importlib.util
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

PAGE = Path('docs/review/differenze-asqueel-genropy-it.html')
BLOCK_IDS = {'Model': 'model', 'Query': 'query', 'Read-Write': 'read-write', 'Adapters': 'adapters'}
TOP_SECTIONS = ['model', 'query', 'read-write', 'adapters', 'da-implementare', 'migrazione',
                'api', 'proposte']
BRANCHES = ['manca', 'diverso', 'nuovo', 'uguale']
BRANCH_OF = {'uguale': 'uguale', 'diverso': 'diverso', 'nuovo': 'nuovo',
             'mancante-temporanea': 'manca', 'mancante-eliminata': 'manca',
             'mancante-sostituita': 'manca'}
LABEL_OF = {'mancante-temporanea': 'temporanea', 'mancante-eliminata': 'eliminata',
            'mancante-sostituita': 'sostituita'}
TWO_SIDED = {'diverso', 'mancante-sostituita'}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source',
        'track', 'wbr'}
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


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []          # (tag, attrs)
        self.sections = []       # section ids in document order, with their parent section id
        self.items = {}          # data-id -> list of dicts
        self.text = {}           # top-level section id -> collected text
        self.errors = []

    def section_path(self):
        return [attrs.get('id') for tag, attrs in self.stack if tag == 'section']

    def handle_starttag(self, tag, attr_list):
        attrs = dict(attr_list)
        if tag in VOID:
            return
        if tag == 'script':
            self.errors.append('the page must not contain <script>')
        if tag == 'section':
            parent = self.section_path()
            self.sections.append((attrs.get('id'), parent[-1] if parent else None))
        if tag in ('article', 'li') and 'data-id' in attrs:
            item = {'tag': tag, 'sections': self.section_path(), 'labels': [], 'details': False,
                    'text': []}
            self.items.setdefault(attrs['data-id'], []).append(item)
        for _tag, open_attrs in self.stack:
            item = open_attrs.get('_item')
            if item is not None:
                if tag == 'details':
                    item['details'] = True
                classes = attrs.get('class', '').split()
                if 'etichetta' in classes:
                    item['labels'] += [c[len('etichetta-'):] for c in classes
                                       if c.startswith('etichetta-')]
        if tag in ('article', 'li') and 'data-id' in attrs:
            attrs['_item'] = self.items[attrs['data-id']][-1]
        self.stack.append((tag, attrs))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1][0] != tag:
            self.errors.append(f'unbalanced </{tag}> (open: {self.stack[-1][0] if self.stack else None})')
            return
        self.stack.pop()

    def handle_data(self, data):
        for _tag, attrs in self.stack:
            if attrs.get('_item') is not None:
                attrs['_item']['text'].append(data)
        path = self.section_path()
        if path:
            self.text.setdefault(path[0], []).append(data)


def main():
    if not PAGE.is_file():
        sys.exit(f'{PAGE} missing')
    source = PAGE.read_text()
    rows = inventory_rows()
    page = Page()
    page.feed(source)
    page.close()
    errors = list(page.errors)
    if page.stack:
        errors.append(f'unclosed tags at end: {[tag for tag, _ in page.stack]}')
    if re.search(r'<link\b|src="https?:|href="https?:[^"]*\.(?:css|js)"', source):
        errors.append('the page must be self-contained: no <link>, no external src, no external css/js')
    if '<html lang="it"' not in source:
        errors.append('the page must declare <html lang="it">')
    top = [sid for sid, parent in page.sections if parent is None]
    if top != TOP_SECTIONS:
        errors.append(f'top-level <section id> must be exactly {TOP_SECTIONS}, found {top}')
    for block_id in BLOCK_IDS.values():
        children = [sid for sid, parent in page.sections if parent == block_id]
        expected = [f'{block_id}-{branch}' for branch in BRANCHES]
        if children != expected:
            errors.append(f'section {block_id}: child sections must be exactly {expected}, found {children}')
    pending = [f'da-implementare-{BLOCK_IDS[b]}' for b in BLOCK_IDS
               if any(r['state'] == 'da-implementare' and r['block'] == b for r in rows.values())]
    children = [sid for sid, parent in page.sections if parent == 'da-implementare']
    if children != pending:
        errors.append(f'section da-implementare: child sections must be exactly {pending}, found {children}')
    for row_id, row in rows.items():
        state, block = row['state'], row['block']
        places = page.items.get(row_id, [])
        if block == 'Migration':
            if places or re.search(rf'\b{re.escape(row_id)}\b', source):
                errors.append(f'{row_id}: Migration rows are not carded or cited')
            continue
        if len(places) != 1:
            errors.append(f'{row_id}: needs exactly one element with data-id, found {len(places)}')
            continue
        item = places[0]
        if state == 'da-implementare':
            where = f'da-implementare-{BLOCK_IDS[block]}'
        else:
            where = f'{BLOCK_IDS[block]}-{BRANCH_OF[state]}'
        if not item['sections'] or item['sections'][-1] != where:
            errors.append(f'{row_id}: inside section {item["sections"][-1:] or None}, expected {where}')
        if state == 'uguale':
            if item['tag'] != 'li':
                errors.append(f'{row_id}: Same items are <li data-id>, not cards')
            continue
        if item['tag'] != 'article':
            errors.append(f'{row_id}: needs a card <article data-id="{row_id}">')
            continue
        if state in LABEL_OF:
            if item['labels'] != [LABEL_OF[state]]:
                errors.append(f'{row_id}: card needs exactly one etichetta-{LABEL_OF[state]}, found {item["labels"]}')
        elif item['labels']:
            errors.append(f'{row_id}: only Missing cards carry a label, found {item["labels"]}')
        text = ''.join(item['text'])
        if state in TWO_SIDED and not ('In GenroPy' in text and 'In asqueel' in text):
            errors.append(f'{row_id}: card needs "In GenroPy" above and "In asqueel" below')
        if not item['details']:
            errors.append(f'{row_id}: card needs a closed <details> block with the files')
    for row_id in sorted(set(page.items) - set(rows)):
        errors.append(f'{row_id}: data-id is not a row of the inventory')
    migration = ''.join(page.text.get('migrazione', []))
    for term in MIGRATION_TERMS:
        if term not in migration:
            errors.append(f'section migrazione must name {term}')
    proposals = ''.join(page.text.get('proposte', []))
    for term in PROPOSAL_TERMS:
        if term not in proposals:
            errors.append(f'section proposte must name {term}')
    for error in errors:
        print(error)
    print(f'{len(rows)} inventory rows checked, {len(errors)} errors')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
