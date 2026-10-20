"""R0: catalogue existing evidence and source contracts; never compile SQL.

Run from the repository root. --check verifies the catalogue without rewriting it.
The original scanner corpus/results and all production/tests/examples are frozen.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / 'docs/design/evidence'
OUT = EVIDENCE / 'legacy-realignment-r0'
OLD = EVIDENCE / 'scanner-comparison'
SNAPSHOTS = Path('/tmp/asqueel-formula-baseline')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n'


def definitions(path):
    """Qualified definitions, with source and AST hashes, without importing code."""
    content = path.read_text()
    lines = content.splitlines(keepends=True)
    result = {}

    def walk(body, prefix=''):
        for node in body:
            if isinstance(node, ast.ClassDef):
                walk(node.body, prefix + node.name + '.')
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = min([node.lineno] + [d.lineno for d in node.decorator_list])
                result[prefix + node.name] = {
                    'line': node.lineno, 'end_line': node.end_lineno,
                    'source_sha256': digest(''.join(lines[start-1:node.end_lineno]).encode()),
                    'ast_sha256': digest(ast.dump(node, include_attributes=False).encode()),
                }
    walk(ast.parse(content).body)
    return result


# These are source definitions, not pytest collection counts. BaseQuerySurface
# is inherited by the two dialect classes; fixture and execution remain separate.
COVERAGE = 'gnrpy/tests/sql/test_compiler_coverage.py'
SURFACE = 'gnrpy/tests/sql/h_query_surface_test.py'
TESTS = {
    'physical': (COVERAGE, [f'TestPhysicalColumns.test_{kind}_column{plural}_{db}'
                           for kind, plural in [('single', ''), ('multiple', 's')]
                           for db in ['pg', 'sqlite']]),
    'embed': (COVERAGE, [f'TestEmbedFieldPars.test_{kind}_param_{db}'
                        for kind in ['column', 'relation'] for db in ['pg', 'sqlite']]),
    'macro': (COVERAGE, [f'TestExpandInRange.test_in_range_in_where_{db}'
                        for db in ['pg', 'sqlite']]),
    'surface': (SURFACE, [f'BaseQuerySurface.{name}' for name in [
        'test_sqltext_property', 'test_test_method', 'test_compiled_property',
        'test_order_by_desc', 'test_where_multiple_conditions', 'test_query_limit',
        'test_query_offset', 'test_columns_with_as_alias', 'test_relation_columns']]),
}

# Algorithm references are source anchors. They are not substitutes for tests.
ALGORITHMS = {
    'discover': ('gnrpy/gnr/sql/gnrsqldata/compiler.py', 'updateFieldDict'),
    'resolve': ('gnrpy/gnr/sql/gnrsqldata/compiler.py', 'getFieldAlias'),
    'select': ('gnrpy/gnr/sql/gnrsqldata/compiler.py', 'compiledQuery'),
    'embed': ('gnrpy/gnr/sql/gnrsqldata/compiler.py', 'embedFieldPars'),
    'template': ('gnrpy/gnr/core/gnrstring.py', 'templateReplace'),
    'split': ('gnrpy/gnr/core/gnrstring.py', 'split'),
    'alias': ('gnrpy/gnr/sql/gnrsql/query.py', 'colToAs'),
    'execute': ('gnrpy/gnr/sql/gnrsql/execute.py', 'execute'),
    'pg': ('gnrpy/gnr/sql/adapters/gnrpostgres.py', 'prepareSqlText'),
    'sqlite': ('gnrpy/gnr/sql/adapters/gnrsqlite.py', 'prepareSqlText'),
    'collections': ('gnrpy/gnr/sql/adapters/_gnrbaseadapter.py', 'adaptTupleListSet'),
}

CONTRACTS = {
    'C01': dict(title='SELECT fisica e clausole già ammesse', phase='R1',
                algorithms=['select', 'discover', 'resolve', 'template'],
                rule='Riferimenti distinti prima della sostituzione; nomi fisici dal modello. '
                     'CASE, COALESCE, cast, ordine, limit/offset senza nuova grammatica.'),
    'C02': dict(title='Proiezioni e alias', phase='R2',
                algorithms=['select', 'split', 'alias'],
                rule='Alias implicito con colToAs; AS duplicato conserva ultima proiezione. '
                     'As misto è una decisione separata M4.'),
    'C03': dict(title='Parametri simbolici nel WHERE', phase='R2',
                algorithms=['embed', 'discover', 'resolve'],
                rule='embedFieldPars precede updateFieldDict sul WHERE; $campo/@relazione '
                     'diventa riferimento se riconosciuto nel modello, non stringa letterale. '
                     'Non estendere la convenzione a tutte le clausole.'),
    'C04': dict(title='Preparazione valori e parametri', phase='R2/R3',
                algorithms=['execute', 'pg', 'sqlite'],
                rule='Nomi Unicode, valori ripetuti e tipizzati; rimuovere un escape iniziale '
                     'da \\$ / \\@ dopo embedFieldPars. Nessuna esecuzione nella compilazione.'),
    'C05': dict(title='Template e letterali', phase='R1/R2/R3',
                algorithms=['discover', 'template', 'execute', 'pg', 'sqlite'],
                rule='Baseline legacy conservata come osservazione; M3 decide se proteggere '
                     'letterali e come interagire con $$, \\: e percentuali. Nessuna scelta implicita.'),
    'C06': dict(title='Commenti', phase='R1/R3',
                algorithms=['discover', 'select', 'pg', 'sqlite'],
                rule='M2 distingue commenti da codice; comprende newline terminale e binding finale. '
                     'Il comportamento protettivo attuale non è ancora approvato.'),
    'C07': dict(title='Collection', phase='R3', algorithms=['collections', 'pg', 'sqlite'],
                rule='IN/NOT IN e vuoti confrontati per valori/NULL; adattamento DBAPI esplicito. '
                     'M1 decide collisioni; non copiare tuple psycopg2 senza verifica psycopg3.'),
    'C08': dict(title='Operatori dei dialetti', phase='R3', algorithms=['pg', 'sqlite'],
                rule='Recuperare REGEXP -> ~* su PostgreSQL e ILIKE -> LIKE su SQLite. '
                     'Le sostituzioni nei letterali appartengono invece a M3.'),
    'C09': dict(title='Relazioni e macro già nel perimetro', phase='R5',
                algorithms=['select', 'resolve', 'embed'],
                rule='Non disponibili nel SELECT minimo gerarchico; portare i test sul nuovo '
                     'albero solo con le rispettive fasi del piano 76.'),
    'C10': dict(title='Diagnostica e limiti', phase='decisione prima del raccordo',
                algorithms=['select', 'discover', 'template', 'pg', 'sqlite'],
                rule='Campo inesistente è errore. Non confondere il rifiuto di input errato '
                     'con parità di classe/messaggio/stadio; errori anticipati da decidere.'),
    'C11': dict(title='Contratto dei kwargs restituiti', phase='R0 decisione/R3',
                algorithms=['select', 'execute', 'pg', 'sqlite'],
                rule='Separare parametri richiesti dal SQL, mapping del chiamante e stato runtime '
                     'jc_kwargs. Non acquisire automaticamente pruning o mutazione degli input.'),
}

DECISIONS = {
    'M1': 'Collisioni dei nomi durante espansione collection: conservarne la prevenzione?',
    'M2': 'Escludere i commenti da riferimenti e binding, compresa la terminazione di riga?',
    'M3': 'Proteggere i letterali SQL: quale interazione con template ed escape legacy?',
    'M4': 'Accettare AS anche con maiuscole/minuscole miste?',
    'M5': 'Anticipare alla compilazione gli errori per parametri mancanti?',
    'D1': 'Supportare $"nome logico"? È un’estensione, distinta dagli alias SQL quotati.',
    'D2': 'Accettare dollar quote/E-string del corpus nel raccordo? La copertura legacy è diversa.',
    'D3': 'Quali kwargs restituire e quale contratto per input immutati/jc_kwargs?',
    'D4': 'Dove diagnosticare stringhe/commenti non chiusi e quale contratto degli errori?',
    'D5': 'Mantenere il rifiuto dei separatori nel compilatore? Il check SQL opzionale resta separato.',
}

# Explicit classification: a new corpus entry cannot silently inherit a default.
GROUPS = [
    ('C01', 'compatibilita_confermata', [],
     'physical sqlparams_year case coalesce cast literal_comma literal_as adjacent_field_operator'),
    ('C02', 'compatibilita_confermata', [], 'alias_lower quoted_alias escaped_alias'),
    ('C02', 'recupero_legacy', [], 'expression_no_alias duplicate_alias'),
    ('C02', 'decisione_aperta', ['M4'], 'alias_mixed'),
    ('C03', 'recupero_legacy', [], 'embed_column_gt embed_column_le bound_literal_field'),
    ('C04', 'recupero_legacy', [], 'bound_escaped_field unicode_param'),
    ('C04', 'compatibilita_confermata', [],
     'bound_quote repeated_bind prefix_params null_binding numeric_binding cast_colon'),
    ('C05', 'decisione_aperta', ['M3'],
     'literal_field literal_unknown_field literal_relation literal_unknown_relation '
     'literal_param literal_param_and_binding literal_colon_escape literal_dollars '
     'literal_quotes literal_percent like_percent macro_in_literal literal_regexp '
     'sqlite_literal_ilike legacy_percent_escape'),
    ('C06', 'decisione_aperta', ['M2'],
     'line_comment block_comment comment_known_field comment_parameter comment_no_newline comment_nested'),
    ('C07', 'compatibilita_confermata', [],
     'in_list not_in_list in_empty not_in_empty_null collection_current_collision'),
    ('C07', 'decisione_aperta', ['M1'], 'collection_collision'),
    ('C08', 'recupero_legacy', [], 'regexp_operator sqlite_ilike_operator'),
    ('C09', 'dipendenza_successiva', [], 'embed_relation relation relation_repeated in_range'),
    ('C10', 'compatibilita_confermata', [], 'unknown_field'),
    ('C10', 'decisione_aperta', ['M5'], 'missing_param'),
    ('C10', 'limite_comune', [], 'unicode_field'),
    ('C10', 'decisione_aperta', ['D1'], 'quoted_logical_field'),
    ('C05', 'decisione_aperta', ['D2', 'M3'], 'dollar_quote tagged_dollar_quote escape_string'),
    ('C10', 'decisione_aperta', ['D4'], 'unclosed_string unclosed_comment'),
    ('C10', 'decisione_aperta', ['D2', 'D4'], 'unclosed_dollar'),
    ('C10', 'decisione_aperta', ['D5'], 'statement_separator'),
    ('C05', 'compatibilita_confermata', [], 'literal_semicolon'),
    ('C11', 'decisione_aperta', ['D3'], 'unused_param'),
]

# Direct provenance only. Other cases have algorithm anchors or are edge probes,
# not retrospectively attributed to original legacy tests.
PROVENANCE = {
    'physical': ('physical', 'Adattamento: altri nomi/dati, due colonne, ordine esplicito; '
                 'non esegue le asserzioni runtime originali.'),
    'sqlparams_year': ('surface', 'test_test_method: stesse columns/where/parametri, '
                        'fixture diversa e verifica delle righe aggiunta.'),
    'embed_column_gt': ('embed', 'test_column_param_{pg,sqlite}: stesso predicato; '
                       'id al posto di count, quattro righe sintetiche anziché invoice_row.'),
    'embed_column_le': ('embed', 'test_column_param_{pg,sqlite}: stesso predicato; '
                       'id al posto di count, quattro righe sintetiche anziché invoice_row.'),
    'embed_relation': ('embed', 'test_relation_param_{pg,sqlite}: adattamento della convenzione; '
                      'tabella, relazione, predicato e asserzioni diversi.'),
    'in_range': ('macro', 'test_in_range_in_where_{pg,sqlite}: campi, intervallo e fixture diversi.'),
}

CONFLICTS = {
    'tests/native_compiler/test_compiler.py': {
        'test_missing_parameters_and_duplicate_aliases': ['C02', 'M5'],
        'test_scanner_preserves_sql_literals_comments_cast_and_percent': ['M2', 'M3', 'D2'],
        'test_escape_string_and_quoted_alias': ['D2', 'M3'],
        'test_quoted_logical_names_work_in_wildcards_predicates_and_returning': ['D1'],
        'test_literal_quoted_field_syntax_is_not_interpreted': ['M3', 'D2'],
        'test_unsupported_or_unknown_expressions_fail': ['D5'],
        'test_unclosed_tokens_fail': ['D4', 'D2'],
    },
    'tests/native_compiler/test_compile_only.py': {
        'test_collection_collision_and_query_reuse_keep_caller_values': ['M1', 'D3'],
        'test_macro_text_inside_literals_comments_and_percent_is_preserved': ['M2', 'M3'],
        'test_missing_macro_parameter_fails_without_execution': ['M5'],
    },
    'tests/object_tree/test_minimal_select.py': {
        'test_scanner_preserves_literals_comments_and_cast': ['M2', 'M3', 'D3'],
        'test_postgres_cast_and_dollar_literal': ['D2', 'M3'],
        'test_unavailable_features_fail_explicitly': ['C02', 'M5', 'D3', 'D5'],
        'test_empty_collection_and_pruned_params': ['D3'],
        'test_reuse_keeps_manglers_and_inputs_separate': ['M1', 'D3'],
    },
}


def catalogue_sources():
    refs = json.loads((OLD / 'legacy-algorithms.json').read_text())
    tests, algorithms = {}, {}
    for branch, ref in refs.items():
        base = SNAPSHOTS / branch
        branch_tests = []
        for group, (path, names) in TESTS.items():
            found = definitions(base/path) if (base/path).exists() else {}
            for name in names:
                branch_tests.append(dict(group=group, path=path, definition=name,
                                         available=name in found, **found.get(name, {})))
        tests[branch] = dict(commit=ref['commit'], definitions=branch_tests,
                             execution='not_run_in_R0')
        if branch == 'legacy':
            assert all(t['available'] for t in branch_tests)
        algorithms[branch] = dict(commit=ref['commit'], definitions={})
        for key, (path, suffix) in ALGORITHMS.items():
            if not (base/path).exists() and key in ['alias', 'execute']:
                path = 'gnrpy/gnr/sql/gnrsql.py'
            found = definitions(base/path)
            matches = [(name, data) for name, data in found.items()
                       if name.rsplit('.', 1)[-1] == suffix]
            assert len(matches) == 1, (branch, path, suffix, matches)
            name, data = matches[0]
            algorithms[branch]['definitions'][key] = dict(path=path, definition=name, **data)
    return tests, algorithms


def observation(engine):
    # Preserve types, kwargs, input mutations and error stage. SQL remains in
    # the immutable source record, indexed and hashed in the manifest.
    keys = ['compile', 'execute', 'params', 'input_after', 'input_parameters',
            'rows', 'columns', 'types', 'error']
    return {k: engine[k] for k in keys if k in engine}


def original_definitions(name, group):
    if group is None:
        return []
    path, names = TESTS[group]
    if name == 'sqlparams_year':
        names = [n for n in names if n.endswith('.test_test_method')]
    elif name.startswith('embed_column'):
        names = [n for n in names if '.test_column_param_' in n]
    elif name == 'embed_relation':
        names = [n for n in names if '.test_relation_param_' in n]
    return [dict(path=path, definition=n) for n in names]


def main(check=False):
    frozen = json.loads((OUT/'frozen-inputs.json').read_text())
    changed = [p for p, sha in frozen.items()
               if not (ROOT/p).exists() or digest((ROOT/p).read_bytes()) != sha]
    assert not changed, ('Frozen inputs changed', changed)
    assert {str(p.relative_to(ROOT)) for area in ['src', 'tests', 'examples']
            for p in (ROOT/area).rglob('*.py')} == {
                p for p in frozen if p.startswith(('src/', 'tests/', 'examples/'))}
    results = json.loads((OLD/'results.json').read_text())
    classification = {}
    for contract, status, decisions, names in GROUPS:
        for name in names.split():
            assert name not in classification, name
            classification[name] = dict(contract=contract, status=status, decisions=decisions)
    assert len(classification) == 71
    assert set(classification) == {r['name'] for r in results}
    assert len(results) == len({(r['name'], r['dialect']) for r in results}) == 132
    cases = []
    for name, state in classification.items():
        records = [(i, r) for i, r in enumerate(results) if r['name'] == name]
        request = records[0][1]['request']
        assert {r['dialect'] for _, r in records} == set(request['dialects'])
        assert all(r['request'] == request for _, r in records)
        if state['status'] == 'compatibilita_confermata':
            for _, r in records:
                if name == 'unknown_field':
                    assert all(e['compile'] == 'error' for e in r['engines'].values())
                else:
                    assert r['same_rows'] and r['same_columns'], name
        group, adaptation = PROVENANCE.get(name, (None, None))
        cases.append(dict(name=name, **state, phase=CONTRACTS[state['contract']]['phase'],
                          request=request, origin=request['origin'],
                          original_test_group=group, adaptation=adaptation,
                          original_test_definitions=original_definitions(name, group),
                          new_tree_dependency=(
                              'R5 relations if M3 retains legacy substitution in literals'
                              if name == 'literal_relation' else
                              'R5 relations; also a lost embedFieldPars compatibility'
                              if name == 'embed_relation' else None),
                          legacy_target=('pending_decision' if state['decisions'] else
                                         'legacy_semantics_not_incidental_error_text_or_kwargs'),
                          observation_source='scanner-comparison/results.json',
                          observations=[dict(index=i, dialect=r['dialect'],
                              source_record_sha256=digest(encoded(r).encode()),
                              legacy=observation(r['engines']['legacy']),
                              current=observation(r['engines']['current'])) for i, r in records]))
    tests, algorithms = catalogue_sources()
    conflicts = []
    for path, names in CONFLICTS.items():
        found = definitions(ROOT/path)
        for name, topics in names.items():
            assert name in found, (path, name)
            conflicts.append(dict(path=path, definition=name, topics=topics, **found[name],
                                  action='unchanged; split only after the relevant contract decision'))
    manifest = dict(
        date='2026-10-14', scope='R0 only; no compiler implementation',
        reference_commit=tests['legacy']['commit'],
        observation_scope='report78 current=previous model; not full hierarchical parity',
        decision_status={key: dict(question=value, status='pending', approved=False)
                         for key, value in DECISIONS.items()},
        global_pending=['D3 applies to kwargs/input mutation in all cases, not only unused_param'],
        regression_modules=['tests/native_compiler/test_compiler.py',
                            'tests/native_compiler/test_compile_only.py',
                            'tests/object_tree/test_minimal_select.py'],
        legacy_compile_only_probe=dict(
            path='docs/design/probes/test_legacy_minimal_select.py',
            file_sha256=digest((ROOT/'docs/design/probes/test_legacy_minimal_select.py').read_bytes()),
            definitions=definitions(ROOT/'docs/design/probes/test_legacy_minimal_select.py'),
            provenance='Existing adapted compile-only probe, not the original runtime suite'),
        classification_meaning='Primary status concerns the stated contract. Equal rows do not '
                               'certify kwargs, input mutation, error classes or the new tree.',
        contracts=CONTRACTS, cases=cases, conflicting_current_tests=conflicts)
    counts = Counter(c['status'] for c in cases)
    summary = dict(cases=len(cases), observations=len(results), primary_status=dict(counts),
                   original_definitions_legacy=len(tests['legacy']['definitions']),
                   original_definitions_available_by_snapshot={
                       name: sum(t['available'] for t in data['definitions'])
                       for name, data in tests.items()},
                   current_conflicting_definitions=len(conflicts),
                   frozen_files=len(frozen), approved_improvements=0)
    matrix = ['# R0 — Matrice dei 71 casi e delle 132 osservazioni', '',
              'Generata da `freeze_legacy_contracts.py`. Le osservazioni sono quelle del rapporto 78.',
              'Nessuna nuova esecuzione SQL. `expected` nel corpus resta un oracolo della sonda:',
              'non prevale sul legacy, soprattutto per stringhe/escape e parametri simbolici.',
              'Le voci compatibili riguardano il contratto indicato; D3 resta trasversale ai kwargs.', '',
              '| Caso | Contratto | Stato | Fase | Decisioni | Dialetti |',
              '| --- | --- | --- | --- | --- | --- |']
    for c in cases:
        matrix.append(f"| `{c['name']}` | {c['contract']} | {c['status']} | {c['phase']} | "
                      f"{', '.join(c['decisions']) or '—'} | {', '.join(c['request']['dialects'])} |")
    matrix += ['', 'I dettagli completi di richieste, risultati, errori, tipi e kwargs sono in',
               '[contracts.json](contracts.json); il SQL originale in',
               '[results.json](../scanner-comparison/results.json).', '',
               'Le 19 definizioni legacy sono congelate in [legacy-tests.json](legacy-tests.json),',
               'con presenza/hash per gli otto snapshot. Non sono 19 nuovi test eseguiti.', '']
    outputs = {'contracts.json': encoded(manifest), 'legacy-tests.json': encoded(tests),
               'algorithm-anchors.json': encoded(algorithms), 'summary.json': encoded(summary),
               'matrix.md': '\n'.join(matrix)}
    for name, content in outputs.items():
        target = OUT/name
        if check:
            assert target.read_text() == content, ('Catalogue drift', str(target))
        else:
            target.write_text(content)
    print(encoded(dict(mode='check' if check else 'freeze', **summary)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    main(parser.parse_args().check)
