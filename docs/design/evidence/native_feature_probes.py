"""Compile-only audit probes; these do not establish legacy equivalence.

Run with an installed asqueel checkout. No connection or SQL is executed.
The output records the last successful phase, errors, and emitted SQL.
"""
import json

from asqueel import SqlDatabaseConfig, build_database


def recipe_for(feature):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            tables = root.db('audit').schemas().schema('app').tables()
            customer = tables.table('customer', pkey='id').columns()
            customer.column('id', dtype='I')
            customer.column('name', dtype='T')
            table = tables.table('invoice', pkey='id')
            columns = table.columns()
            columns.column('id', dtype='I')
            columns.column('amount', dtype='N')
            columns.column('customer_id', dtype='I').relation(
                'app.customer.id', x_name='customer', foreign_key=True)
            virtuals = table.virtual_columns()
            if feature == 'formula':
                virtuals.formulaColumn('double', sql_formula='$amount * 2', dtype='N')
            elif feature == 'formula_chain':
                virtuals.formulaColumn('double', sql_formula='$amount * 2', dtype='N')
                virtuals.formulaColumn('quad', sql_formula='$double * 2', dtype='N')
            elif feature == 'alias':
                virtuals.aliasColumn('customer_name', relation_path='@customer.name')
            elif feature == 'formula_select':
                virtuals.formulaColumn('value', select='SELECT 1', dtype='I')
            elif feature == 'formula_exists':
                virtuals.formulaColumn('value', exists='SELECT 1', dtype='B')
            elif feature == 'subquery':
                virtuals.subQueryColumn('value', query='SELECT 1', mode='json')
            elif feature == 'python':
                virtuals.pyColumn('value', py_method='compute_value', dtype='N')
            elif feature == 'composite_value':
                table.composites().compositeColumn('key_pair', columns='id,customer_id')
    return Recipe


CASES = [
    ('formula', '$double', {}, 'compiled'),
    ('formula_chain', '$quad', {}, 'compiled'),
    ('alias', '$customer_name', {}, 'compiled'),
    ('formula_select', '$value', {}, 'compiled'),
    ('formula_exists', '$value', {}, 'compiled'),
    ('subquery', '$value', {}, 'compiled'),
    ('python', '$value', {}, 'compiled'),
    ('composite_value', '$key_pair', {}, 'compiled'),
    ('to_one', '@customer.name AS customer_name', {}, 'compiled'),
    ('group_by', '$customer_id, SUM($amount) AS total', {'group_by': '$customer_id'}, 'compiled'),
    ('distinct', '$customer_id', {'distinct': True}, 'compiled'),
    ('count', '*', {}, 'count'),
    ('selection', '*', {}, 'selection'),
    ('relation_function', '@customer.count() AS n', {}, 'compiled'),
    ('aggregate_rows', '*', {'aggregateRows': True}, 'compiled'),
]


def run(case):
    name, columns, options, terminal = case
    outcome = {'case': name, 'phase': 'declaration', 'executed_sql': False}
    db = None
    try:
        recipe = recipe_for(name)()
        recipe.create()
        outcome['phase'] = 'resolution'
        db = build_database(recipe)
        outcome['phase'] = 'query_construction'
        query = db.table('invoice').query(columns=columns, **options)
        outcome['phase'] = 'terminal'
        if terminal == 'compiled':
            outcome['sql'] = query.compiled.sql
            outcome['status'] = 'compiled_only'
        else:
            getattr(query, terminal)()
            outcome['status'] = 'returned'
    except Exception as error:
        outcome['status'] = 'error'
        outcome['error_type'] = type(error).__name__
        outcome['error'] = str(error)
    finally:
        if db is not None:
            db.close()
    return outcome


if __name__ == '__main__':
    print(json.dumps([run(case) for case in CASES], indent=2, ensure_ascii=False))
