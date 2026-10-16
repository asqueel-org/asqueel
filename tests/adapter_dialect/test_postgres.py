"""Dialect rendering uses plans directly, independently of asqueel resolution."""
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
    assert text(PostgresDialect().render(plan)) == expected.replace(' WHERE ', '\nWHERE ') + '\nRETURNING "t0"."id" AS "id"'


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
    QueryPlan('delete', TableRef('s', 't'), where=concat('   ')),
    QueryPlan('insert', TableRef('s', 't'), where=concat('TRUE')),
    select(limit=-1), select(limit=True), select(dialect='sqlite'),
    select(where=concat(Parameter('missing'))),
    QueryPlan('select', TableRef('s', 't')),
])
def test_malformed_plans_are_rejected(plan):
    with pytest.raises(ValueError):
        PostgresDialect().render(plan)


def test_clauses_have_fixed_separators_without_repairing_expression_text():
    dialect = PostgresDialect()
    statement = dialect.render(select(
        where=concat('TRUE -- predicate'), order_by=concat('1 -- order'), limit=0,
        joins=(Join(TableRef('s', 't', 't1'), concat('TRUE -- join')),)))
    assert 'TRUE -- join\nWHERE TRUE -- predicate\nORDER BY 1 -- order\nLIMIT 0' in text(statement)
    assignments = (Assignment('first', concat('1 -- value')), Assignment('second', concat(Parameter('p'))))
    update = QueryPlan('update', TableRef('s', 't'), assignments=assignments,
                       where=concat('FALSE -- guard'), projections=(projection(),), params={'p': 2})
    rendered = text(dialect.render(update))
    assert 'SET "first" = 1 -- value, "second" = <bind:p>\nWHERE FALSE -- guard\nRETURNING' in rendered
    insert = QueryPlan('insert', TableRef('s', 't'), assignments=assignments, params={'p': 2})
    assert 'VALUES (1 -- value, <bind:p>)' in text(dialect.render(insert))
