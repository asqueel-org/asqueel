"""Native Bag extraction uses ordinary formulas and isolated parameter scopes."""

import pytest

from asqueel import SqlDatabaseConfig, build_database
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.drivers.sqlite import SqliteDriver


def source(backend='postgresql'):
    config = SqlDatabaseConfig()
    pkg = config.source.db('bags', implementation=backend).packages().package('app')
    pkg.options().type('money', dtype='N', size='14,2')
    table = pkg.table('item', pkey='id')
    table.column('id', dtype='L')
    table.column('details', dtype='X', sqlname='payload')
    table.column('parent_id', dtype='L').relation('app.item.id')
    specs = [('weight', 'specs.weight', 'N'), ('color', 'specs.color', 'T'),
             ('price', 'specs.price', 'money'), ('position', '#0.#1', 'T'),
             ('unit', 'specs.weight?unit', 'T'), ('first', 'repeated', 'T'),
             ('missing', 'absent', 'T'), ('integer', 'typed.integer', 'I'),
             ('bigint', 'typed.bigint', 'L'), ('real', 'typed.real', 'R'),
             ('boolean', 'typed.boolean', 'B'), ('date', 'typed.date', 'D'),
             ('time', 'typed.time', 'H'), ('stamp', 'typed.stamp', 'DH'),
             ('utc', 'typed.utc', 'DHZ')]
    for name, path, dtype in specs:
        table.bagItemColumn(name, bagcolumn='$details', itempath=path, dtype=dtype)
    table.bagItemColumn('default', bagcolumn='$details', itempath='specs.color')
    table.bagItemColumn('related', bagcolumn='@parent_id.details', itempath='specs.weight', dtype='N')
    table.aliasColumn('alias', '$weight')
    table.formulaColumn('total', '$weight + $price + :calculated_path', var_calculated_path=2, dtype='N')
    table.formulaColumn('nested', select=dict(table='app.item', columns='$weight',
                        where='$id=#THIS.parent_id'), dtype='N')
    return config


@pytest.fixture(autouse=True)
def no_io(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Bag column compilation attempted database I/O')
    for driver in [PsycopgDriver, SqliteDriver]:
        monkeypatch.setattr(driver, 'connect', forbidden)
        monkeypatch.setattr(driver, 'execute', forbidden)


@pytest.fixture
def db():
    with build_database(source()) as database:
        yield database
