import pytest

from asqueel import SqlDatabase, SqlDatabaseConfig
from asqueel.configuration import _owned_handler
from asqueel.write_compiler import WriteCompiler


def bind(source):
    return SqlDatabase(model=source.render(mode='objects_tree'), config=_owned_handler(source))


@pytest.fixture
def db():
    source = SqlDatabaseConfig()
    pkg = source.source.db('compiler', implementation='postgresql').packages().package(
        'app', sqlschema='Actual "Schema')
    customer = pkg.table('customer', pkey='id')
    customer.column('id', dtype='L')
    customer.column('name', sqlname='full%name', x_ui_label='Name')
    invoice = pkg.table('invoice', pkey='id', sqlname='Order')
    invoice.column('id', dtype='L')
    invoice.column('customer_id', dtype='L').relation('app.customer.id')
    invoice.column('amount', dtype='N')
    invoice.formulaColumn('double', '$amount * 2', dtype='N')
    invoice.formulaColumn('quad', '$double * 2', dtype='N')
    log = pkg.table('log')
    log.column('note')
    with bind(source) as database:
        yield database


def writer(db):
    return WriteCompiler(db.dialect, db.driver)


def model(db, name):
    return db.table(name).model


def test_insert_values_mapping_and_default_values(db):
    query = writer(db).insert(model(db, 'app.customer'), {'id': 1, 'name': "Robert'); DROP TABLE x;--"}, {})
    assert 'DROP TABLE' not in query.sql
    assert query.params['name'] == "Robert'); DROP TABLE x;--"
    assert 'DEFAULT VALUES' in writer(db).insert(model(db, 'app.customer'), {}, {}).sql


@pytest.mark.xfail(strict=True, reason="asqueel#19: a '%' in a physical column name is not escaped for psycopg")
def test_insert_escapes_percent_in_physical_names(db):
    query = writer(db).insert(model(db, 'app.customer'), {'id': 1, 'name': 'x'}, {})
    assert '"full%%name"' in query.sql


def test_update_collision_returning_and_line_comment(db):
    query = writer(db).update(model(db, 'app.invoice'), {'id': 1, 'amount': 4}, {})
    assert query.params['__pkey__0'] == 1
    assert query.params['amount'] == 4
    assert '"amount"=' in query.sql


def test_writes_need_predicate(db):
    with pytest.raises(KeyError):
        writer(db).delete(model(db, 'app.invoice'), {'amount': 1}, {})
    with pytest.raises(KeyError):
        writer(db).update(model(db, 'app.invoice'), {'amount': 1}, {})
    with pytest.raises(ValueError, match='has no primary key'):
        writer(db).delete(model(db, 'app.log'), {'note': 'x'}, {})
    with pytest.raises(ValueError, match='has no primary key'):
        writer(db).update(model(db, 'app.log'), {'note': 'x'}, {})
    deleted = writer(db).delete(model(db, 'app.invoice'), {'id': 1}, {})
    assert deleted.sql.endswith('WHERE "id"=%(__pkey__0)s')


def test_dml_rejects_formula_writes_and_relation_paths(db):
    table = model(db, 'app.invoice')
    inserted = writer(db).insert(table, {'id': 1, 'double': 3, '@customer_id': {'id': 1}}, {})
    assert '"double"' not in inserted.sql
    assert 'double' not in inserted.params and '@customer_id' not in inserted.params
    deleted = writer(db).delete(table, {'id': 1, 'double': 3, '@customer_id': 1}, {})
    assert dict(deleted.params) == {'__pkey__0': 1}


@pytest.mark.xfail(strict=True, reason='asqueel#20: quoted logical names $"..." are not supported; '
                                       'DML binds non-identifier logical names wrongly')
@pytest.mark.parametrize('name', ['display name', 'a-b', 'città', 'αριθμός', '50%', 'a"b'])
def test_quoted_logical_names_work_in_wildcards_predicates_and_returning(name):
    source = SqlDatabaseConfig()
    table = source.source.db('quoted', implementation='postgresql').packages().package('app').table('t', pkey='id')
    table.column('id', dtype='L')
    table.column(name)
    with bind(source) as db:
        reference = '$"' + name.replace('"', '""') + '"'
        selected = db.compiler.select('app.t', where=reference + ' = :value', sqlparams={'value': 'x'},
                                      order_by=reference)
        assert selected.columns[1].name == name
        assert selected.sql.count('"t0".') == 4
        assert '%(value)s' in selected.sql
        for query in [writer(db).insert(model(db, 'app.t'), {'id': 1, name: 'x'}, {}),
                      writer(db).update(model(db, 'app.t'), {'id': 1, name: 'x'}, {})]:
            assert query.params[name] == 'x'
            assert set(query.params) <= {'id', name, '__pkey__0'}


def test_returning_formula_that_requires_join_is_rejected():
    source = SqlDatabaseConfig()
    pkg = source.source.db('joined', implementation='postgresql').packages().package('app')
    customer = pkg.table('customer', pkey='id')
    customer.column('id')
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id')
    invoice.column('customer_id').relation('app.customer.id')
    invoice.formulaColumn('display', '@customer_id.id')
    with bind(source) as db:
        table = model(db, 'app.invoice')
        for query in [writer(db).insert(table, {'id': 1}, {}),
                      writer(db).update(table, {'id': 1}, {}),
                      writer(db).delete(table, {'id': 1}, {})]:
            assert 'display' not in query.sql
            assert 'JOIN' not in query.sql


def test_result_source_preserves_stable_identity_across_alias_and_physical_names():
    source = SqlDatabaseConfig()
    pkg = source.source.db('identity', implementation='postgresql').packages().package('app')
    customer = pkg.table('customer', pkey='id', sqlname='renamed_customer')
    customer.column('id', x_identity='stable:customer:id')
    customer.column('name', sqlname='renamed_name', x_identity='stable:customer:name', x_ui_label='Customer')
    invoice = pkg.table('invoice', pkey='customer_id')
    invoice.column('customer_id').relation('app.customer.id')
    with bind(source) as db:
        direct = db.compiler.select('app.customer', '$name AS display')
        related = db.compiler.select('app.invoice', '@customer_id.name AS display')
        for query in (direct, related):
            assert query.columns[0].source == 'stable:customer:name'
            assert query.columns[0].name == 'display'
            assert query.columns[0].ui == {'label': 'Customer'}
        assert db.compiler.select('app.invoice').columns[0].source == 'app.invoice.customer_id'
