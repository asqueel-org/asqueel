"""Audit source/model coverage without changing the renderer or accessing a DB.

Run with the audit environment and PYTHONPATH=src:../asqueel-migration/src:
  python docs/design/evidence/audit-invoice-render-coverage.py GENROPY_ROOT OUTPUT

The legacy snapshots are independent expectations, never native producer input.
Nonliteral columns below include generated AND dynamically declared columns;
the report must not treat that set as proven option provenance.
"""
from __future__ import annotations

import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import runpy
import sys


REPO = Path(__file__).resolve().parents[3]
ORACLE = REPO / 'tests/oracles/test_invoice_pg'
EXCLUDED_NATIVE_TABLES = {'sys.locked_record': 'User decision; report 52, D-02'}
METHOD_FAMILIES = {
    'table': 'base', 'column': 'base', 'sysFields': 'sys_fields',
    'aliasColumn': 'alias', 'formulaColumn': 'formula',
    'pyColumn': 'python_column', 'subQueryColumn': 'subquery',
    'bagItemColumn': 'bag_item', 'compositeColumn': 'composite',
    'relation': 'relations', 'index': 'indexes', 'joinColumn': 'virtual_relation',
    'aliasTable': 'virtual_relation', 'subtable': 'subtable',
}
KEYWORD_FAMILIES = {
    'counter': 'auto_counter', 'hierarchical': 'hierarchical',
    'hierarchical_caption_field': 'hierarchical', 'df': 'dynamic_fields',
    'subfields': 'dynamic_fields_column', 'md5': 'record_hash', 'audit': 'audit',
    'sysrecords': 'system_records', 'sysRecord_masterfield': 'system_records',
    'multi_tenant': 'tenant', 'retention_policy': 'retention',
    'broadcast': 'broadcast', 'archivable': 'archive', 'checkpref': 'enabled_when',
    'pkey_columns': 'pkey_columns', 'pkey_columns_joiner': 'pkey_columns',
    'encrypted': 'encryption', 'values': 'validation',
    'default': 'column_data', 'defaultFrom': 'column_data', 'sql_value': 'column_data',
    'readOnly': 'column_data', 'unmodifiable': 'column_data',
}
OPTION_FAMILIES = {
    'hierarchical', 'auto_counter', 'relative_index', 'dynamic_fields',
    'record_hash', 'full_update', 'audit', 'system_records', 'protection',
    'diagnostics', 'release', 'partition', 'tenant', 'retention', 'broadcast',
    'archive', 'enabled_when', 'attachments', 'numbering',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def children(node, section):
    return node.get('children', {}).get(section, {}).get('children', {})


def literal_name(declaration):
    if not declaration['arguments']:
        return None
    try:
        value = ast.literal_eval(declaration['arguments'][0])
    except (ValueError, SyntaxError):
        return None
    return value if isinstance(value, str) else None


def grammar_probes():
    from asqueel import SqlDatabaseConfig, SqlMigrationRenderer

    checks = {
        'formula_legacy_bindings': lambda t: t.formulaColumn(
            'v', sql_formula=':x + #s', var_x=1,
            select_s={'table': 'invc.other', 'columns': '$id'}),
        'alias_static': lambda t: t.aliasColumn('v', '@other_id.id', static=True),
        'py_template': lambda t: t.pyColumn(
            'v', py_method='templateColumn', template_name='day_cal', template_localized=True),
        'py_attachment_metadata': lambda t: t.pyColumn(
            'v', py_method='filepath_endpoint_url', outdatedWatermark=None, static=True),
        'relation_on_duplicate_false': lambda t: t.column('other_id').relation(
            'other.id', on_duplicate=False),
        'subquery_aggregate': lambda t: t.subQueryColumn(
            'v', query={'table': 'invc.other', 'columns': '$id'}, mode='sum'),
    }
    results = {}
    for name, check in checks.items():
        config = SqlDatabaseConfig()
        table = config.source.db('audit').packages().package('invc').table('probe')
        try:
            node = check(table)
            config.validate_source()
            results[name] = {'accepted': True, 'attributes': {
                k: v for k, v in node.attr.items() if k != '_meta'}}
        except (ValueError, TypeError) as error:
            results[name] = {'accepted': False, 'error': str(error)}
    config = SqlDatabaseConfig()
    table = config.source.db('audit').packages().package(
        'invc', sqlschema='invc').table('probe', pkey='id')
    table.column('id', size='22')
    table.column('bag', dtype='X')
    table.column('prefix', size=':20')
    physical = SqlMigrationRenderer(config).render()['root']['schemas']['invc']['tables']['invc_probe']
    results['native_physical_projection'] = {
        name: node['attributes'] for name, node in physical['columns'].items()}
    config = SqlDatabaseConfig()
    table = config.source.db('audit').packages().package(
        'adm', sqlschema='adm').table('group', pkey='code')
    table.column('code', size=':15')
    table.column('no2fa_alternative_group', size=':15').relation(
        'adm.group.code', on_delete='set_null')
    native = SqlMigrationRenderer(config).render()['root']['schemas']['adm']['tables']['adm_group']
    legacy = json.loads((ORACLE / 'physical.json').read_text())['root']['schemas']['adm']['tables']['adm_group']
    results['set_null_implicit_deferral'] = {
        'native': native['relations'], 'legacy': legacy['relations']}
    return results


def audit(legacy_root):
    scanner = runpy.run_path(str(Path(__file__).with_name('inventory-test-invoice.py')))
    inventory = scanner['inventory'](legacy_root)
    manifest = json.loads((ORACLE / 'manifest.json').read_text())
    model = json.loads((ORACLE / 'model.json').read_text())['children']
    physical = json.loads((ORACLE / 'physical.json').read_text())['root']['schemas']
    changes = [record['file'] for record in manifest['model_sources']
               if digest(legacy_root / record['file']) != record['sha256']]
    imported_changes = [name for name, sha in manifest['imported_legacy_sources'].items()
                        if digest(legacy_root / name) != sha]
    artifacts_ok = {name: digest(ORACLE / name) == sha
                    for name, sha in manifest['artifacts'].items()}
    expected_files = {r['file'] for r in manifest['model_sources']}
    actual_files = {r['file'] for r in inventory['records']}
    assert not changes and not imported_changes and all(artifacts_ok.values())
    assert expected_files == actual_files, 'Snapshot source membership changed'
    for folder in ('custom', 'plugin'):
        path = (legacy_root / inventory['instance']).parent / folder
        assert not list(path.rglob('*.py')), 'Additional instance contributions require review'

    tables = {}
    package_records = []
    for record in inventory['records']:
        if record['role'] == 'package':
            package_records.append(record)
            continue
        path = Path(record['file'])
        namespace = path.parent.name if record['role'] == 'contribution' else record['package']
        key = f'{namespace}.{path.stem}'
        entry = tables.setdefault(key, {'sources': [], 'families': set(), 'literal_columns': set()})
        entry['sources'].append({k: record[k] for k in ('file', 'sha256', 'role', 'bases', 'methods')})
        entry['sources'][-1]['declaration_locations'] = [
            {'line': d['line'], 'method': d['method']} for d in record['declarations']]
        for declaration in record['declarations']:
            method = declaration['method']
            if method in METHOD_FAMILIES:
                entry['families'].add(METHOD_FAMILIES[method])
            if method == 'column' and literal_name(declaration):
                entry['literal_columns'].add(literal_name(declaration))
            for keyword in declaration['keywords']:
                if keyword in KEYWORD_FAMILIES:
                    entry['families'].add(KEYWORD_FAMILIES[keyword])
                if keyword.startswith('validate_'):
                    entry['families'].add('validation')
                if keyword.startswith('partition_'):
                    entry['families'].add('partition')
                if method == 'table' and keyword.startswith('group_'):
                    entry['families'].add('groups')
        if 'AttachmentTable' in record['bases']:
            entry['families'].update({'base', 'attachments', 'sys_fields', 'auto_counter',
                                      'relations', 'python_column'})
        for method in record['methods']:
            if method['name'].startswith('sysRecord_'):
                entry['families'].add('system_records')
            if method['name'].startswith('counter_'):
                entry['families'].add('numbering')

    package_counts = {}
    all_model_keys = {f'{pkg}.{name}' for pkg, node in model.items() for name in children(node, 'tables')}
    assert set(tables) == all_model_keys, 'Not every model has original-source evidence'
    for pkg, node in model.items():
        counts = Counter()
        for name, table in children(node, 'tables').items():
            key = f'{pkg}.{name}'
            entry = tables[key]
            columns = children(table, 'columns')
            virtuals = children(table, 'virtual_columns')
            actual_physical = physical[pkg]['tables'][pkg + '_' + name]
            assert set(columns) == set(actual_physical['columns'])
            counts.update(tables=1, columns=len(columns), legacy_virtual_entries=len(virtuals),
                          foreign_keys=len(actual_physical['relations']),
                          indexes=len(actual_physical['indexes']),
                          constraints=len(actual_physical['constraints']))
            if '__record_pointer' in virtuals:
                counts['sys_fields_tables'] += 1
                entry['families'].add('sys_fields')
            entry['families'] = sorted(entry['families'])
            entry['literal_columns'] = sorted(entry['literal_columns'])
            entry['expanded_columns_not_literal_in_local_sources'] = sorted(set(columns) - set(entry['literal_columns']))
            entry['expected_physical_columns'] = list(columns)
            entry['storage_normalizations'] = {
                col: {'model': {k: value['attributes'].get(k) for k in ('dtype', 'size')},
                      'physical': {k: actual_physical['columns'][col]['attributes'].get(k)
                                   for k in ('dtype', 'size')}}
                for col, value in columns.items()
                if any(value['attributes'].get(k) != actual_physical['columns'][col]['attributes'].get(k)
                       for k in ('dtype', 'size'))}
            entry['expected_virtual_entries'] = list(virtuals)
            entry['expected_subtables'] = list(children(table, 'subtables'))
            entry['expected_table_aliases'] = list(children(table, 'table_aliases'))
            entry['physical_counts'] = {k: len(actual_physical[k])
                                       for k in ('columns', 'relations', 'indexes', 'constraints')}
            entry['expected_model_indexes'] = list(children(table, 'indexes'))
            entry['explicit_syscode'] = '__syscode' in entry['literal_columns']
            entry['generated_syscode'] = '__syscode' in columns and not entry['explicit_syscode']
            entry['release_column'] = '__release' in columns
            entry['syscode_dependent_virtuals'] = [n for n, v in virtuals.items()
                                                  if '__syscode' in str(v['attributes'])]
            entry['native_status'] = ('excluded_from_native_scope' if key in EXCLUDED_NATIVE_TABLES
                                      else 'not_certified; original declarations still to port')
        package_counts[pkg] = dict(counts)

    tree = ast.parse((REPO / 'examples/model_grammar/configure.py').read_text())
    example_tables = sorted(f'{call.func.value.id}.{ast.literal_eval(call.args[0])}'
                            for call in ast.walk(tree) if isinstance(call, ast.Call)
                            and isinstance(call.func, ast.Attribute) and call.func.attr == 'table'
                            and isinstance(call.func.value, ast.Name))
    families = {name: sorted(key for key, entry in tables.items() if name in entry['families'])
                for name in sorted(OPTION_FAMILIES | {f for t in tables.values() for f in t['families']})}
    native_sources = ['src/asqueel/' + name for name in (
        'elements.py', 'model_elements.py', 'semantic_elements.py', 'option_elements.py',
        'option_validation.py', 'model_expansion.py', 'model_source.py', 'projection.py', 'builder.py')]
    return {
        'scope': 'Phase 0: checked original sources + unchanged independent legacy capture + native probes; no DB I/O',
        'legacy_sources_changed': changes, 'legacy_imported_sources_changed': imported_changes,
        'verified_model_source_count': len(manifest['model_sources']),
        'verified_imported_source_count': len(manifest['imported_legacy_sources']),
        'oracle_sha256': manifest['artifacts'], 'artifact_integrity': artifacts_ok,
        'native_source_sha256': {name: digest(REPO / name) for name in native_sources},
        'package_counts': package_counts, 'package_sources': package_records,
        'original_inventory': 'test-invoice-model-inventory.json',
        'keywords_by_method': inventory['keywords_by_method'],
        'native_example_partial_tables': example_tables,
        'excluded_native_tables': EXCLUDED_NATIVE_TABLES,
        'native_target_table_counts': {
            pkg: sum(key.startswith(pkg + '.') and key not in EXCLUDED_NATIVE_TABLES for key in tables)
            for pkg in model},
        'system_records_scope': 'excluded; structural divergences recorded in report 52, D-01',
        'native_complete_corpus_verified': False,
        'families': families, 'tables': dict(sorted(tables.items())),
        'grammar_probes': grammar_probes(),
    }


if __name__ == '__main__':
    result = audit(Path(sys.argv[1]).resolve())
    Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'packages': result['package_counts'],
                      'tables_with_source_evidence': len(result['tables']),
                      'partial_example_tables': len(result['native_example_partial_tables']),
                      'artifact_integrity': result['artifact_integrity']}, ensure_ascii=False))
