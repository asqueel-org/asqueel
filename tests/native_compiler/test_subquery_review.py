"""Independent regression probes for subquery declaration loss."""
import pytest

from genro_sql import Column, PostgresCompiler, ResolvedModel, SqlBuilder, Table, resolve_model


@pytest.mark.parametrize('formula', ["'#total'", "1 /* #total */", "1 -- #total\n"])
def test_named_subquery_in_protected_text_is_not_a_consumed_declaration(formula):
    builder = SqlBuilder()
    table = builder.source.db('d').schemas().schema('s').tables().table('t', pkey='id')
    table.columns().column('id', dtype='I')
    table.virtual_columns().formulaColumn(
        'v', sql_formula=formula,
        select_total={'table': 's.t', 'where': 'TRUE', 'columns': '$id'},
    )
    with pytest.raises(ValueError, match='[Uu]nused|not used'):
        PostgresCompiler(resolve_model(builder)).select('s.t', columns='$v')


@pytest.mark.parametrize('attributes', [
    {'formula': '2', 'select': {'table': 's.t', 'where': 'TRUE', 'columns': '1'}},
    {'select': {'table': 's.t', 'where': 'TRUE', 'columns': '1'},
     'exists': {'table': 's.t', 'where': 'TRUE', 'columns': '1'}},
])
def test_manual_column_cannot_silently_discard_an_executable_definition(attributes):
    model = ResolvedModel({'s.t': Table('t', 's', {
        'id': Column('id', dtype='I'), 'v': Column('v', **attributes),
    })})
    with pytest.raises(ValueError):
        PostgresCompiler(model).select('s.t', columns='$v')
