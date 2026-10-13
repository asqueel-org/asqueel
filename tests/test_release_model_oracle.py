"""Independent legacy evidence for the full release-model acceptance corpus.

These checks pin the scope and nontrivial generated declarations, not the new
implementation. No GenroPy import, live instance or PostgreSQL is needed.
"""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from asqueel_migration import StructureValidator


ORACLE = Path(__file__).parent / 'oracles' / 'test_invoice_pg'


@pytest.fixture(scope='module')
def legacy_model():
    return json.loads((ORACLE / 'model.json').read_text())


@pytest.fixture(scope='module')
def legacy_physical():
    return json.loads((ORACLE / 'physical.json').read_text())


def table(model, package, name):
    return model['children'][package]['children']['tables']['children'][name]


def test_corpus_has_all_packages_and_the_interpackage_contribution(legacy_model):
    manifest = json.loads((ORACLE / 'manifest.json').read_text())
    counts = {name: len(pkg['children']['tables']['children'])
              for name, pkg in legacy_model['children'].items()}
    assert counts == manifest['table_counts'] == {'sys': 17, 'adm': 40, 'invc': 18}
    contributions = [s['file'] for s in manifest['model_sources'] if s['role'] == 'contribution']
    assert contributions == ['projects/gnrcore/packages/adm/model/_packages/sys/task.py']
    assert 'user_id' in table(legacy_model, 'sys', 'task')['children']['columns']['children']


def test_normalized_physical_oracle_is_valid_and_contains_the_contributed_fk(legacy_physical):
    StructureValidator().validate(legacy_physical)
    schemas = legacy_physical['root']['schemas']
    assert {key: len(value['tables']) for key, value in schemas.items()} == {
        'sys': 17, 'adm': 40, 'invc': 18}
    tables = [tbl for schema in schemas.values() for tbl in schema['tables'].values()]
    assert sum(len(tbl['columns']) for tbl in tables) == 796
    assert sum(len(tbl['relations']) for tbl in tables) == 58
    task = schemas['sys']['tables']['sys_task']
    targets = [r['attributes'] for r in task['relations'].values()]
    assert any(r['columns'] == ['user_id'] and r['related_schema'] == 'adm'
               and r['related_table'] == 'adm_user' for r in targets)


def test_inherited_attachment_and_dynamic_fields_are_expanded(legacy_model):
    attachment = table(legacy_model, 'adm', 'htmltemplate_atc')['children']
    assert {'maintable_id', 'filepath', 'info', '_row_count'} <= attachment['columns']['children'].keys()
    assert {'adapted_url', 'fileurl', 'missing_file', 'full_external_url'} <= (
        attachment['virtual_columns']['children'].keys())
    product_type = table(legacy_model, 'invc', 'product_type')['children']
    assert {'parent_id', 'hierarchical_pkey', 'hierarchical_description',
            '_row_count', '_h_count', 'df_fields', 'df_fbcolumns',
            'df_custom_templates', 'df_colswidth'} <= product_type['columns']['children'].keys()


def test_semantic_model_preserves_features_absent_from_migration_json(legacy_model, legacy_physical):
    customer = table(legacy_model, 'invc', 'customer')['children']
    assert len(customer['subtables']['children']) == 4
    account = customer['columns']['children']['account_name']['attributes']
    assert account['validate_notnull'] is True
    assert account['validate_len'] == '2:40'
    assert customer['columns']['children']['access_token']['attributes']['encrypted'] == 'X'
    assert {'__record_pointer', 'n_invoices', 'customer_score'} <= customer['virtual_columns']['children'].keys()
    physical = legacy_physical['root']['schemas']['invc']['tables']['invc_customer']['columns']
    assert 'n_invoices' not in physical
    assert '__is_draft' in physical
    assert '__mod_user' not in physical  # Explicit legacy profile, not the new default.


def test_artifacts_match_provenance_and_source_is_parseable():
    manifest = json.loads((ORACLE / 'manifest.json').read_text())
    for filename, expected in manifest['artifacts'].items():
        content = (ORACLE / filename).read_bytes()
        assert hashlib.sha256(content).hexdigest() == expected
        assert b'/Users/' not in content
        assert b'object at 0x' not in content
    root = ET.parse(ORACLE / 'source.xml').getroot()
    assert {node.tag for node in root.find('packages')} == {'sys', 'adm', 'invc'}
