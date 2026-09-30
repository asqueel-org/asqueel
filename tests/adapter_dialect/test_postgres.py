"""Dialect rendering uses plans directly, independently of Genro resolution."""
from dataclasses import replace

import pytest

from asqueel.contracts import ResultColumn, UnsupportedFeatureError
from asqueel.dialects.postgres import PostgresDialect
from asqueel.query_plan import (
    Assignment, Fragment, Identifier, Join, Parameter, Projection, QueryPlan,
    TableRef, concat,
)


def text(statement):
    return ''.join(part if isinstance(part, str) else f'<bind:{part.name}>'
                   for part in statement.parts)


def projection():
    return Projection(concat(Identifier('t0'), '.', Identifier('id')), 'id', ResultColumn('id', 'I'))


def select(**options):
    return QueryPlan('select', TableRef('public', 'rows'), projections=(projection(),), **options)


def test_plan_renders_identifiers_parameters_and_zero_pagination_without_driver_format():
    dialect = PostgresDialect()
    plan = select(where=concat(Identifier('id'), ' = ', Parameter('key')), params={'key': 2}, limit=0, offset=0)
    statement = dialect.render(plan)
    assert text(statement) == 'SELECT "t0"."id" AS "id" FROM "public"."rows" AS "t0" WHERE "id" = <bind:key> LIMIT 0 OFFSET 0'
    assert statement.params['key'] == 2
    assert statement.columns == (projection().column,)
    assert any(isinstance(part, Parameter) for part in statement.parts)
    assert dialect.quote_identifier('amount%"') == '"amount%"""'


def test_left_join_uses_only_resolved_table_references():
    joined = Join(TableRef('sales', 'customer', 't1'), concat(
        Identifier('t0'), '.', Identifier('customer_id'), ' = ', Identifier('t1'), '.', Identifier('id')))
    statement = PostgresDialect().render(select(joins=(joined,)))
    assert 'LEFT JOIN "sales"."customer" AS "t1" ON "t0"."customer_id" = "t1"."id"' in text(statement)


@pytest.mark.parametrize(('operation', 'expected'), [
    ('insert', 'INSERT INTO "s"."t" AS "t0" ("amount") VALUES (<bind:value>)'),
    ('update', 'UPDATE "s"."t" AS "t0" SET "amount" = <bind:value> WHERE TRUE'),
    ('delete', 'DELETE FROM "s"."t" AS "t0" WHERE TRUE'),
])
def test_dml_rendering(operation, expected):
    plan = QueryPlan(operation, TableRef('s', 't'),
                     assignments=() if operation == 'delete' else (Assignment('amount', concat(Parameter('value'))),),
                     where=None if operation == 'insert' else concat('TRUE'),
                     params={'value': 3}, projections=(projection(),))
    assert text(PostgresDialect().render(plan)) == expected + ' RETURNING "t0"."id" AS "id"'


def test_default_values_and_returning_are_independent_capabilities():
    plan = QueryPlan('insert', TableRef('s', 't'))
    assert text(PostgresDialect().render(plan)).endswith(' DEFAULT VALUES')
    dialect = PostgresDialect(capabilities=PostgresDialect.capabilities - {'returning_insert'})
    assert dialect.render(plan)
    with pytest.raises(UnsupportedFeatureError, match='returning_insert'):
        dialect.render(replace(plan, projections=(projection(),)))
    with pytest.raises(UnsupportedFeatureError, match='default_values'):
        PostgresDialect(capabilities=frozenset({'insert'})).render(plan)


@pytest.mark.parametrize('plan', [
    QueryPlan('update', TableRef('s', 't')),
    QueryPlan('delete', TableRef('s', 't'), where=Fragment()),
    QueryPlan('delete', TableRef('s', 't'), where=concat(' /* comment */ -- more')),
    QueryPlan('insert', TableRef('s', 't'), where=concat('TRUE')),
    select(limit=-1), select(limit=True), select(dialect='sqlite'),
    select(where=concat(Parameter('missing'))),
    QueryPlan('select', TableRef('s', 't')),
])
def test_malformed_plans_are_rejected(plan):
    with pytest.raises(ValueError):
        PostgresDialect().render(plan)


def test_disabled_features_and_join_variants_fail_explicitly():
    with pytest.raises(UnsupportedFeatureError, match='select'):
        PostgresDialect(capabilities=frozenset()).render(select())
    with pytest.raises(UnsupportedFeatureError, match='join kind'):
        PostgresDialect().render(select(joins=(Join(TableRef('s', 't', 't1'), concat('TRUE'), 'right'),)))


def test_scanner_protects_sql_lexical_regions_and_exposes_cast_operator():
    sql = '''E'\\\' $ignored' "id" $"field" $$:no $field$$ /* outer /*nested*/ $x */ -- :hidden
:x::integer'''
    tokens = list(PostgresDialect().tokens(sql))
    assert ''.join(value for _, value in tokens) == sql
    assert ('field', '$"field"') in tokens
    assert ('operator', '::') in tokens
    assert any(kind == 'line_comment' for kind, _ in tokens)
    assert [v for k, v in tokens if k == 'string'] == ["'\\\' $ignored'", '$$:no $field$$']


@pytest.mark.parametrize('expression', ["'open", '/* unclosed', '$body$unclosed', '$"unclosed'])
def test_scanner_rejects_unclosed_regions(expression):
    with pytest.raises(ValueError):
        list(PostgresDialect().tokens(expression))


@pytest.mark.parametrize('name', ['', '\x00', 'x' * 64, 'à' * 32])
def test_identifier_boundaries_are_explicit(name):
    with pytest.raises(ValueError):
        PostgresDialect().quote_identifier(name)


def test_manual_projection_comment_cannot_hide_alias_or_from():
    expression = concat('1 -- comment')
    plan = QueryPlan('select', TableRef('missing_schema', 'missing_table'), projections=(
        Projection(expression, 'value', ResultColumn('value')),))
    statement = PostgresDialect().render(plan)
    assert text(statement) == ('SELECT 1 -- comment\n AS "value" FROM '
                               '"missing_schema"."missing_table" AS "t0"')
    assert plan.projections[0].expression == expression  # Input plan remains unchanged.


def test_manual_comments_cannot_hide_other_clauses_or_assignment_separators():
    dialect = PostgresDialect()
    statement = dialect.render(select(
        where=concat('TRUE -- predicate'), order_by=concat('1 -- order'), limit=0,
        joins=(Join(TableRef('s', 't', 't1'), concat('TRUE -- join')),)))
    assert 'TRUE -- join\n WHERE TRUE -- predicate\n ORDER BY 1 -- order\n LIMIT 0' in text(statement)
    assignments = (Assignment('first', concat('1 -- value')), Assignment('second', concat(Parameter('p'))))
    update = QueryPlan('update', TableRef('s', 't'), assignments=assignments,
                       where=concat('FALSE -- guard'), projections=(projection(),), params={'p': 2})
    rendered = text(dialect.render(update))
    assert 'SET "first" = 1 -- value\n, "second" = <bind:p> WHERE FALSE -- guard\n RETURNING' in rendered
    insert = QueryPlan('insert', TableRef('s', 't'), assignments=assignments, params={'p': 2})
    assert 'VALUES (1 -- value\n, <bind:p>)' in text(dialect.render(insert))


def test_fragment_comment_detection_handles_parts_and_protected_percent_strings():
    plan = select(where=Fragment(('TRUE ', '-- ', 'tail')), order_by=concat("'%--literal'"))
    rendered = text(PostgresDialect().render(plan))
    assert "WHERE TRUE -- tail\n ORDER BY '%--literal'" in rendered
