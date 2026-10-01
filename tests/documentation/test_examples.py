"""Execute published examples so the guide and its downloadable tutorial agree."""
from tests.unit_of_work import completed
from pathlib import Path
import re
import runpy
from uuid import uuid4

import pytest

from asqueel import CompiledQuery
from tests.native_support import postgres_dsn

GUIDE = Path(__file__).resolve().parents[2] / 'docs' / 'guide'


def python_blocks(name):
    return re.findall(r'^```python\n(.*?)^```', (GUIDE / name).read_text(), re.M | re.S)


@pytest.mark.parametrize('page', [
    'configuration-grammars.md', 'models.md', 'formulas.md', 'configuration.md',
])
def test_self_contained_offline_model_examples(page):
    # Each first block promises a complete declaration/render without database I/O.
    exec(compile(python_blocks(page)[0], str(GUIDE / page), 'exec'), {})


def test_all_guide_python_fragments_have_valid_syntax():
    for path in GUIDE.glob('*.md'):
        for index, block in enumerate(python_blocks(path.name)):
            compile(block, f'{path}:python-block-{index + 1}', 'exec')


@pytest.mark.postgresql
def test_downloadable_tutorial():
    tutorial = runpy.run_path(str(GUIDE / '_examples' / 'shop_tutorial.py'))
    rows = tutorial['run'](postgres_dsn())
    assert [row['id'] for row in rows] == [10, 11]


@pytest.mark.postgresql
def test_application_query_guide_against_tutorial_data():
    tutorial = runpy.run_path(str(GUIDE / '_examples' / 'shop_tutorial.py'))
    schema = 'genro_doc_queries_' + uuid4().hex
    with tutorial['open_shop'](postgres_dsn(), schema) as db:
        tutorial['create_tables'](db, schema)
        try:
            tutorial['seed'](db)
            namespace = {'db': db}
            # The page states these blocks run against the tutorial's seed data.
            for index, block in enumerate(python_blocks('queries.md')):
                exec(compile(block, f'queries.md:block-{index + 1}', 'exec'), namespace)
            # Document the empty-list case too, not just the nonempty ANY example.
            with completed(db):
                assert db.table('sales.customer').query(
                    where='$id = ANY(:ids)', sqlparams={'ids': []},
                ).fetch() == []
        finally:
            db.rollback()
            with completed(db):
                db.execute(CompiledQuery(f'DROP SCHEMA "{schema}" CASCADE'))


@pytest.mark.postgresql
def test_quickstart_as_published(monkeypatch):
    monkeypatch.setenv('ASQUEEL_DSN', postgres_dsn())
    exec(compile(python_blocks('quickstart.md')[0], 'quickstart.md', 'exec'), {})


@pytest.mark.postgresql
def test_application_environment_examples():
    tutorial = runpy.run_path(str(GUIDE / '_examples' / 'shop_tutorial.py'))
    schema = 'genro_doc_env_' + uuid4().hex
    with tutorial['open_shop'](postgres_dsn(), schema) as db:
        tutorial['create_tables'](db, schema)
        try:
            tutorial['seed'](db)
            # First five blocks cover the application API. Later blocks use a
            # different policy model or the explicitly independent executor.
            for index, block in enumerate(python_blocks('environment.md')[:5]):
                namespace = {'db': db, 'Shop': tutorial['Shop']}
                exec(compile(block, f'environment.md:block-{index + 1}', 'exec'), namespace)
        finally:
            db.rollback()
            with completed(db):
                db.execute(CompiledQuery(f'DROP SCHEMA "{schema}" CASCADE'))
