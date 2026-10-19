"""SQL for insert, update, delete and table locks on the hierarchical model.

Ported from the GenroPy adapter (reference fa35e5ad,
gnr/sql/adapters/_gnrbaseadapter.py: prepareRecordData, insert, update,
delete; _gnrbasepostgresadapter.lockTable). It is separate from the query
compiler: statements are legacy SQL text with ``:name`` parameters, prepared by
the adapter into the common CompiledQuery and executed by ``db.execute``.
"""
from __future__ import annotations

import datetime
import json
import re
from decimal import Decimal

from genro_bag import Bag

from .common import split_names, sql_attribute_declared

#: Physical types whose value the database assigns on insert.
_GENERATED_KEY_DTYPES = frozenset({'serial', 'serial4'})
#: PostgreSQL table lock modes accepted by ``lock_table``.
LOCK_MODES = frozenset({'ACCESS SHARE', 'ROW SHARE', 'ROW EXCLUSIVE', 'SHARE UPDATE EXCLUSIVE', 'SHARE',
                        'SHARE ROW EXCLUSIVE', 'EXCLUSIVE', 'ACCESS EXCLUSIVE'})
#: Legacy GnrClassCatalog parsers of the typed texts a composite key can hold,
#: by suffix and its aliases (gnrclasses.py standardClasses).
_TYPED_TEXT_PARSERS = {
    **dict.fromkeys(('L', 'I', 'LONG', 'LONGINT', 'INT', 'INTEGER'), int),
    **dict.fromkeys(('R', 'F', 'REAL', 'FLOAT'), float),
    **dict.fromkeys(('N', 'NUMERIC', 'DECIMAL'), Decimal),
    **dict.fromkeys(('B', 'BOOL', 'BOOLEAN'), lambda text: text.upper() in ('Y', 'TRUE', 'YES', '1')),
    **dict.fromkeys(('D', 'DATE'), datetime.date.fromisoformat),
    **dict.fromkeys(('DH', 'DHZ', 'DATETIME', 'DT'), datetime.datetime.fromisoformat),
    **dict.fromkeys(('H', 'HZ', 'TIME'), datetime.time.fromisoformat),
}
_TYPED_TEXT = re.compile(r'^(.*)::(' + '|'.join(_TYPED_TEXT_PARSERS) + r')$', re.DOTALL)


class JSONTypedEncoder(json.JSONEncoder):
    """Legacy gnrstring.JSONTypedEncoder: temporal and decimal values as typed text."""

    def default(self, o):
        if isinstance(o, datetime.time):
            return f'{o}::H'
        if isinstance(o, Decimal):
            return f'{o}::N'
        if isinstance(o, datetime.datetime):
            return f'{o}::DH'
        if isinstance(o, datetime.date):
            return f'{o}::D'
        return super().default(o)


def toTypedJSON(values):
    """The serialized composite key: legacy toTypedJSON."""
    return json.dumps(values, cls=JSONTypedEncoder)


def fromTypedJSON(text):
    """Legacy fromTypedJSON on a serialized key: a list whose typed texts become values."""
    values = json.loads(text)
    if not isinstance(values, list):
        raise ValueError(f'a serialized composite key is a JSON list, not {text!r}')
    return [_from_typed_text(value) for value in values]


def _from_typed_text(value):
    match = _TYPED_TEXT.match(value) if isinstance(value, str) else None
    if match is None:
        return value
    text, dtype = match.groups()
    return _TYPED_TEXT_PARSERS[dtype](text)


class WriteCompiler:
    """Build write statements for one database's adapter."""

    def __init__(self, adapter):
        self.adapter = adapter

    # ------------------------------------------------------------------
    #  Names
    # ------------------------------------------------------------------

    def sql_fullname(self, table):
        quote = self.adapter.adaptSqlName
        return '.'.join(quote(name) for name in (table.sqlschema, table.sqlname) if name)

    def pkeys(self, table):
        """Physical key columns: the components of a composite key, else the key."""
        pkey = table.pkey
        if not pkey:
            raise ValueError(f'{table.fullname} has no primary key')
        composite = table.composites.get(pkey)
        if composite is not None:
            return tuple(split_names(composite.attributes['columns']))
        return tuple(split_names(pkey))

    # ------------------------------------------------------------------
    #  Record data
    # ------------------------------------------------------------------

    def prepare_record_data(self, table, record):
        """prepareRecordData: the values a statement may bind.

        Keys starting with ``@``, the ``pkey`` key and virtual columns are
        dropped. A Bag becomes its XML, an empty Bag None. Other keys that are not physical columns are kept as
        parameters but never become SQL columns, as in the legacy adapter.
        Every ``sql_value`` column absent from the record is added with None,
        so its expression is always emitted.
        """
        virtual = set(table.virtual_columns) | set(table.composites)
        data = {}
        for key, value in record.items():
            if key.startswith('@') or key == 'pkey' or key in virtual:
                continue
            if isinstance(value, Bag):
                value = value.to_xml() if len(value) else None
            data[str(key)] = value
        for name, column in table.columns.items():
            if 'sql_value' in column.attributes and name not in data:
                data[name] = None
        return data

    # ------------------------------------------------------------------
    #  Statements
    # ------------------------------------------------------------------

    def insert(self, table, record, snapshot):
        """INSERT of the non-None physical columns plus every sql_value column."""
        data = self.prepare_record_data(table, record)
        sql = self._insert_sql(table, data)
        sql += self._returning(table, self._insert_returning(table, data), 'returning_insert')
        return self.adapter.prepare_sql(sql, data, snapshot)

    def insert_many(self, table, records, snapshot):
        """insertMany: consecutive records with the same SQL share one statement.

        Returns ``(compiled, params)`` pairs for ``db.executemany``; no RETURNING,
        as in the legacy insertMany.
        """
        groups: list[tuple] = []
        for record in records:
            data = self.prepare_record_data(table, record)
            compiled = self.adapter.prepare_sql(self._insert_sql(table, data), data, snapshot)
            if groups and groups[-1][0].sql == compiled.sql:
                groups[-1][1].append(compiled.params)
            else:
                groups.append((compiled, [compiled.params]))
        return groups

    def _insert_sql(self, table, data):
        quote = self.adapter.adaptSqlName
        names, values = [], []
        for key, value in data.items():
            column = table.columns.get(key)
            if column is None:
                continue
            sql_value = column.attributes.get('sql_value')
            if value is not None or sql_value is not None:
                names.append(quote(column.sqlname))
                # A newline ends a line comment inside sql_value before the next token.
                values.append(f'{sql_value}\n' if sql_value else f':{key}')
        target = self.sql_fullname(table)
        if names:
            return f'INSERT INTO {target}({",".join(names)}) VALUES ({",".join(values)})'
        return f'INSERT INTO {target} DEFAULT VALUES'

    def update(self, table, record, snapshot, *, pkey=None, old_record=None):
        """UPDATE of every physical column present in the record, None included.

        The key comes from old_record, then from pkey, then from the record
        itself, as in the legacy adapter.
        """
        data = self.prepare_record_data(table, record)
        quote = self.adapter.adaptSqlName
        assignments = []
        for key in list(data):
            column = table.columns.get(key)
            if column is None:
                continue
            sql_value = column.attributes.get('sql_value')
            assignments.append(f'{quote(column.sqlname)}=' + (f'{sql_value}\n' if sql_value else f':{key}'))
        if not assignments:
            raise ValueError(f'{table.fullname}: UPDATE requires at least one column')
        keys = self.pkeys(table)
        if old_record:
            key_values = [old_record[name] for name in keys]
        elif pkey is not None:
            key_values = self.key_values(table, pkey)
        else:
            key_values = [data[name] for name in keys]
        where = self._key_where(table, keys, key_values, data)
        sql = f'UPDATE {self.sql_fullname(table)} SET {",".join(assignments)} WHERE {where}'
        sql += self._returning(table, self._update_returning(table), 'returning_update')
        return self.adapter.prepare_sql(sql, data, snapshot)

    def delete(self, table, record, snapshot):
        """DELETE of one record by its key, with the SQL column names."""
        keys = self.pkeys(table)
        params = {}
        where = self._key_where(table, keys, [record[name] for name in keys], params)
        sql = f'DELETE FROM {self.sql_fullname(table)} WHERE {where}'
        return self.adapter.prepare_sql(sql, params, snapshot)

    def update_selection(self, table, plan, values, snapshot):
        """UPDATE of the rows a query selects: ``WHERE pk IN (<its key SELECT>)``.

        ``plan`` is the query's SELECT reduced to the key columns, prepared by
        the query compiler; its filters, order and limit decide the rows.
        """
        data = self.prepare_record_data(table, values)
        quote = self.adapter.adaptSqlName
        assignments = []
        for key in list(data):
            column = table.columns.get(key)
            if column is None:
                continue
            sql_value = column.attributes.get('sql_value')
            assignments.append(f'{quote(column.sqlname)}=' + (f'{sql_value}\n' if sql_value else f':{key}'))
        if not assignments:
            raise ValueError(f'{table.fullname}: UPDATE requires at least one column')
        where = self._selection_where(table, plan, data)
        sql = f'UPDATE {self.sql_fullname(table)} SET {",".join(assignments)} WHERE {where}'
        return self.adapter.prepare_sql(sql, data, snapshot)

    def delete_selection(self, table, plan, snapshot):
        """DELETE of the rows a query selects: ``WHERE pk IN (<its key SELECT>)``."""
        params = {}
        where = self._selection_where(table, plan, params)
        return self.adapter.prepare_sql(f'DELETE FROM {self.sql_fullname(table)} WHERE {where}', params, snapshot)

    def lock_table(self, table, snapshot, mode='ACCESS EXCLUSIVE', nowait=False):
        """lockTable; SQLite has no table lock and takes the write reservation instead.

        The SQLite statement is the one a ``for_update`` query runs inside a
        transaction: an UPDATE of no row, which the driver opens a transaction for.
        """
        if mode not in LOCK_MODES:
            raise ValueError(f'lock mode must be one of {", ".join(sorted(LOCK_MODES))}, not {mode!r}')
        if self.adapter.dialect == 'sqlite':
            names = self.pkeys(table) if table.pkey else tuple(table.columns)
            column = self.adapter.adaptSqlName(table.columns[names[0]].sqlname)
            return self.adapter.prepare_sql(
                f'UPDATE {self.sql_fullname(table)} SET {column}={column} WHERE 0', {}, snapshot)
        sql = f'LOCK {self.sql_fullname(table)} IN {mode} MODE{" NOWAIT" if nowait else ""}'
        return self.adapter.prepare_sql(sql, {}, snapshot)

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    def key_values(self, table, pkey):
        """The physical key values of ``pkey``; a composite key is its serialized string."""
        keys = self.pkeys(table)
        if len(keys) == 1:
            return [pkey]
        values = fromTypedJSON(pkey) if isinstance(pkey, str) else None
        if values is None or len(values) != len(keys):
            raise ValueError(f'{table.fullname}: a composite key is the serialized string of its '
                             f'{len(keys)} members, as toTypedJSON writes it (e.g. \'[1, 2]\'), not {pkey!r}')
        # The compositeColumn read on SQLite holds a boolean member as the number 1 or 0.
        return [bool(value) if table.columns[name].dtype == 'B' and type(value) is int else value
                for name, value in zip(keys, values)]

    def _key_where(self, table, keys, values, params):
        quote = self.adapter.adaptSqlName
        conditions = []
        for index, (name, value) in enumerate(zip(keys, values)):
            parameter = f'__pkey__{index}'
            params[parameter] = value
            conditions.append(f'{quote(table.columns[name].sqlname)}=:{parameter}')
        return ' AND '.join(conditions)

    def _selection_where(self, table, plan, params):
        shared = set(plan.params) & set(params)
        if shared:
            raise ValueError(f'{table.fullname}: parameters used by both the query and the values: {sorted(shared)}')
        params.update(plan.params)
        quote = self.adapter.adaptSqlName
        keys = ','.join(quote(table.columns[name].sqlname) for name in self.pkeys(table))
        return f'({keys}) IN ({plan.get_sqltext(self.adapter)})'

    @staticmethod
    def _insert_returning(table, data):
        """Columns whose inserted value the database decides."""
        names = []
        for name, column in table.columns.items():
            attributes = column.attributes
            missing = data.get(name) is None
            if attributes.get('sql_value') is not None or sql_attribute_declared(attributes, 'generatedExpression'):
                names.append(name)
            elif missing and (sql_attribute_declared(attributes, 'default')
                              or attributes.get('dtype') in _GENERATED_KEY_DTYPES):
                names.append(name)
        return names

    @staticmethod
    def _update_returning(table):
        return [name for name, column in table.columns.items()
                if column.attributes.get('sql_value') is not None
                or sql_attribute_declared(column.attributes, 'generatedExpression')]

    def _returning(self, table, names, capability):
        if not names or capability not in self.adapter.capabilities:
            return ''
        quote = self.adapter.adaptSqlName
        projections = ','.join(f'{quote(table.columns[name].sqlname)} AS {quote(name)}' for name in names)
        return f' RETURNING {projections}'
