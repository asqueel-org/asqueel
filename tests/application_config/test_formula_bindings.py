import pytest

from asqueel import SqlDatabaseConfig, UnsupportedFeatureError, build_database


def recipe(local=None):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            tables = root.db('bindings').schemas().schema('app').tables()
            invoice = tables.table('invoice', pkey='id')
            invoice.columns().column('id', dtype='I')
            lines = tables.table('line', pkey='id').columns()
            for name in ('id', 'invoice_id', 'amount'):
                lines.column(name, dtype='I')
            definition = dict(table='app.line', columns='SUM($amount)',
                              where='$invoice_id=#THIS.id AND $amount>:floor')
            if local is not None:
                definition['sqlparams'] = local
            invoice.virtual_columns().formulaColumn('total', select=definition, dtype='I')
    return Recipe


def test_query_keyword_consumed_only_in_child_scope_is_recognized():
    with build_database(recipe()) as db:
        compiled = db.table('invoice').query(columns='$total', floor=5).compiled
        assert compiled.input_parameters == ('floor',)
        assert list(compiled.params.values()) == [5]
        assert 'floor' not in compiled.params


def test_local_parameter_shadow_does_not_consume_unused_caller_keyword():
    with build_database(recipe({'floor': 7})) as db:
        with pytest.raises(UnsupportedFeatureError, match='unused keyword'):
            db.table('invoice').query(columns='$total', floor=5).compiled
        compiled = db.table('invoice').query(columns='$total', sqlparams={'floor': 5}).compiled
        assert list(compiled.params.values()) == [7]
        assert compiled.input_parameters == ()


def test_generated_binding_cannot_capture_explicit_caller_name():
    with build_database(recipe()) as db:
        compiled = db.table('invoice').query(
            columns='$total', where='$id=:s1_floor', floor=5, s1_floor=99).compiled
        assert compiled.input_parameters == ('floor', 's1_floor')
        assert compiled.params['s1_floor'] == 99
        assert sorted(compiled.params.values()) == [5, 99]
