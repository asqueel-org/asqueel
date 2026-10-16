"""R1 contracts: legacy field maps and substitution, without database I/O."""
from collections import Counter
from dataclasses import replace

import pytest

from asqueel._legacy_sql import FieldReferences, template_replace
from asqueel.compiler import _TreeContext
from tests.object_tree import test_minimal_select as minimal

db = minimal.db
no_io = minimal.no_io


def test_resolve_distinct_fields_once_across_clauses(db, monkeypatch):
    calls = Counter()
    original = _TreeContext.field

    def field(context, table, alias, name):
        calls[name] += 1
        return original(context, table, alias, name)

    monkeypatch.setattr(_TreeContext, 'field', field)
    query = db.table('sales.invoice').query(
        columns=','.join(f'COALESCE($total,0) AS value_{i}' for i in range(100)),
        where='$total>=:amount AND $id>0', order_by='$total,$id', amount=3)
    compiled = query.compiled
    assert calls == {'total': 1, 'id': 2}  # legacy seeds pkey before discovering explicit id
    assert compiled.sql.count('COALESCE("t0"."total",0)') == 100
    assert compiled.params == {'amount': 3}
    again = query.compiled
    assert again == compiled
    assert calls == {'total': 2, 'id': 4}


def test_field_resolution_does_not_use_previous_expression_scanner(db, monkeypatch):
    import asqueel.compiler as compiler
    assert not hasattr(compiler, '_Context')
    assert not hasattr(compiler, '_split')
    assert not hasattr(db.dialect, 'tokens')
    compiled = db.table('sales.invoice').query(
        columns="COALESCE($total,0) AS amount, '$id' AS literal",
        where='$id=:id', id=1).compiled
    assert 'COALESCE("t0"."total",0)' in compiled.sql
    assert "'\"t0\".\"id\"'" in compiled.sql
    assert compiled.params == {'id': 1}


def test_legacy_alias_rules_needed_by_projection_split(db):
    compiled = db.table('sales.invoice').query(
        columns='$total * 2, $id AS value, $total AS value, $label as label').compiled
    assert [c.name for c in compiled.columns] == ['_total___2', 'value', 'label']
    assert '"t0"."id" AS value' not in compiled.sql
    assert '"t0"."total" AS value' in compiled.sql


def test_quoted_logical_reference_is_not_translated(db):
    # Same lack of interpretation as legacy; SQL execution is deliberately
    # outside this test. Quoting physical SQL names remains the adapter's job.
    compiled = db.table('sales.invoice').query(columns='$"id" AS value').compiled
    assert '$"id" AS value' in compiled.sql
    assert '"t0"."id"' not in compiled.sql


def test_projection_metadata_does_not_repair_authored_sql(db):
    # The legacy leaves these invalid expressions to the database; compile only.
    mixed = db.table('sales.invoice').query(columns='$id As code').compiled
    repeated = db.table('sales.invoice').query(columns='$id AS code AS other').compiled
    assert '"t0"."id" As code AS "_id_As_code"' in mixed.sql
    assert '"t0"."id" AS code AS other' in repeated.sql


def test_separator_not_a_new_core_validation_rule(db):
    # Compile only, as in the comparison corpus. Never execute this statement.
    compiled = db.table('sales.invoice').query(columns='$id', where='$id=1; SELECT 2').compiled
    assert '"t0"."id"=1; SELECT 2' in compiled.sql


def test_template_column_safe_mode_and_clause_strict_mode(db):
    safe = db.table('sales.invoice').query(columns='$id, 1+$ AS extra').compiled
    assert '1+$ AS extra' in safe.sql
    with pytest.raises(ValueError, match='Invalid placeholder'):
        db.table('sales.invoice').query(columns='$id', where='$id=1 AND $').compiled


def test_empty_template_map_and_dollar_escape_follow_legacy(db):
    unmapped = db.table('sales.invoice').query(columns="'$$' AS value").compiled
    mapped = db.table('sales.invoice').query(columns="'$$' AS value", order_by='$id').compiled
    assert "'$' AS" in unmapped.sql  # pkey seeds the legacy template map
    assert "'$' AS" in mapped.sql


def test_resolver_loop_includes_references_discovered_during_resolution():
    references = FieldReferences()
    references.discover('$formula + $formula')
    calls = []

    def resolve(path):
        calls.append(path)
        if path == 'formula':
            references.discover('$dependency')
        elif path == 'dependency':
            references.discover('$physical')
        return 'resolved_' + path

    references.resolve(resolve)
    assert calls == ['formula', 'dependency', 'physical']
    assert references.substitute('$formula + $physical') == 'resolved_formula + resolved_physical'


def test_relation_references_flatten_with_legacy_paths():
    refs = FieldReferences()
    text = refs.discover('$id, @customer_id.name, @customer_id.name, @customer_id.@city_id.code')
    assert text == '$id, $_customer_id_name, $_customer_id_name, $_customer_id__city_id_code'
    assert refs.paths == {'id': 'id', '_customer_id_name': '@customer_id.name',
                          '_customer_id__city_id_code': '@customer_id.@city_id.code'}


def test_template_conditional_blocks_keep_legacy_semantics():
    assert template_replace('${AND $id=1} ${AND $absent=2}', {'id': 't0.id'}) == 'AND t0.id=1 '
    assert template_replace('${id}', {'id': 't0.id'}) == ''


def test_environment_snapshot_and_preparation_are_separate(db, monkeypatch):
    plan = db.compiler.plan_select('sales.invoice', columns='$id',
                                  where='$issued=:env_workdate', sqlparams={})
    captured = []
    prepare = db.driver.prepare_sql

    def record(sql, params, snapshot):
        captured.append((sql, dict(params)))
        return prepare(sql, params, snapshot)

    monkeypatch.setattr(db.driver, 'prepare_sql', record)
    with db.tempEnv(workdate='changed after planning'):
        compiled = db.compiler.compile_plan(plan)
    assert len(captured) == 1
    assert ':env_workdate' in captured[0][0]
    assert compiled.params['env_workdate'] == plan.params['env_workdate']
    assert not compiled.input_parameters
    assert db._connections == {}


def test_wrong_dialect_plan_still_rejected(db):
    plan = db.compiler.plan_select('sales.invoice', columns='$id')
    other = 'sqlite' if plan.dialect == 'postgresql' else 'postgresql'
    with pytest.raises(ValueError):
        db.compiler.compile_plan(replace(plan, dialect=other))


def test_r3_prepares_values_and_unicode_without_recompiling_fields(db):
    compiled = db.table('sales.invoice').query(
        columns='$id', where='$total>:soglia_è AND $label=:value',
        sqlparams={'soglia_è': 3, 'value': b'\\$id'}).compiled
    assert compiled.params == {'soglia_è': 3, 'value': '$id'}
    marker = '%(soglia_è)s' if db.dialect.name == 'postgresql' else ':soglia_è'
    assert marker in compiled.sql
    assert compiled.input_parameters == ('soglia_è', 'value')


def test_r3_missing_environment_value_is_none_as_in_legacy(db):
    compiled = db.table('sales.invoice').query(columns='$id', where='$id=:env_absent').compiled
    assert compiled.params == {'env_absent': None}
    assert compiled.environment.keys == ('absent',)
    assert not compiled.input_parameters
