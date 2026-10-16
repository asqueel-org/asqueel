"""SQL for insert, update, delete and table locks on the hierarchical model.

Ported from the GenroPy adapter (reference fa35e5ad,
gnr/sql/adapters/_gnrbaseadapter.py: prepareRecordData, insert, update,
delete; _gnrbasepostgresadapter.lockTable). It is separate from the query
compiler: statements are legacy SQL text with ``:name`` parameters, prepared by
the driver into the common CompiledQuery and executed by ``db.execute``.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from .common import split_names

#: Physical types whose value the database assigns on insert.
_GENERATED_KEY_DTYPES = frozenset({'serial', 'serial4'})


class WriteCompiler:
    """Build write statements for one database's dialect and driver."""

    def __init__(self, dialect, driver):
        self.dialect = dialect
        self.driver = driver

    # ------------------------------------------------------------------
    #  Names
    # ------------------------------------------------------------------

    def sql_fullname(self, table):
        quote = self.dialect.quote_identifier
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
        dropped. Other keys that are not physical columns are kept as
        parameters but never become SQL columns, as in the legacy adapter.
        Every ``sql_value`` column absent from the record is added with None,
        so its expression is always emitted.
        """
        virtual = set(table.virtual_columns) | set(table.composites)
        data = {}
        for key, value in record.items():
            if key.startswith('@') or key == 'pkey' or key in virtual:
                continue
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
        return self.driver.prepare_sql(sql, data, snapshot)

    def insert_many(self, table, records, snapshot):
        """insertMany: consecutive records with the same SQL share one statement.

        Returns ``(compiled, params)`` pairs for ``db.executemany``; no RETURNING,
        as in the legacy insertMany.
        """
        groups: list[tuple] = []
        for record in records:
            data = self.prepare_record_data(table, record)
            compiled = self.driver.prepare_sql(self._insert_sql(table, data), data, snapshot)
            if groups and groups[-1][0].sql == compiled.sql:
                groups[-1][1].append(compiled.params)
            else:
                groups.append((compiled, [compiled.params]))
        return groups

    def _insert_sql(self, table, data):
        quote = self.dialect.quote_identifier
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
        quote = self.dialect.quote_identifier
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
            key_values = self._key_values(table, keys, pkey)
        else:
            key_values = [data[name] for name in keys]
        where = self._key_where(table, keys, key_values, data)
        sql = f'UPDATE {self.sql_fullname(table)} SET {",".join(assignments)} WHERE {where}'
        sql += self._returning(table, self._update_returning(table), 'returning_update')
        return self.driver.prepare_sql(sql, data, snapshot)

    def delete(self, table, record, snapshot):
        """DELETE of one record by its key, with the SQL column names."""
        keys = self.pkeys(table)
        params = {}
        where = self._key_where(table, keys, [record[name] for name in keys], params)
        sql = f'DELETE FROM {self.sql_fullname(table)} WHERE {where}'
        return self.driver.prepare_sql(sql, params, snapshot)

    def update_selection(self, table, plan, values, snapshot):
        """UPDATE of the rows a query selects: ``WHERE pk IN (<its key SELECT>)``.

        ``plan`` is the query's SELECT reduced to the key columns, prepared by
        the query compiler; its filters, order and limit decide the rows.
        """
        data = self.prepare_record_data(table, values)
        quote = self.dialect.quote_identifier
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
        return self.driver.prepare_sql(sql, data, snapshot)

    def delete_selection(self, table, plan, snapshot):
        """DELETE of the rows a query selects: ``WHERE pk IN (<its key SELECT>)``."""
        params = {}
        where = self._selection_where(table, plan, params)
        return self.driver.prepare_sql(f'DELETE FROM {self.sql_fullname(table)} WHERE {where}', params, snapshot)

    def lock_table(self, table, snapshot, mode='ACCESS EXCLUSIVE', nowait=False):
        """lockTable; SQLite has no table lock and gets no statement."""
        if self.dialect.name == 'sqlite':
            return None
        sql = f'LOCK {self.sql_fullname(table)} IN {mode} MODE{" NOWAIT" if nowait else ""}'
        return self.driver.prepare_sql(sql, {}, snapshot)

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    def _key_values(self, table, keys, pkey):
        if len(keys) == 1:
            return [pkey]
        if isinstance(pkey, Mapping):
            return [pkey[name] for name in keys]
        if isinstance(pkey, Sequence) and not isinstance(pkey, str) and len(pkey) == len(keys):
            return list(pkey)
        raise ValueError(f'{table.fullname}: a composite key needs a mapping or a sequence of {len(keys)} values')

    def _key_where(self, table, keys, values, params):
        quote = self.dialect.quote_identifier
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
        quote = self.dialect.quote_identifier
        keys = ','.join(quote(table.columns[name].sqlname) for name in self.pkeys(table))
        return f'({keys}) IN ({plan.get_sqltext(self.dialect)})'

    @staticmethod
    def _insert_returning(table, data):
        """Columns whose inserted value the database decides."""
        names = []
        for name, column in table.columns.items():
            attributes = column.attributes
            missing = data.get(name) is None
            if attributes.get('sql_value') is not None or attributes.get('generated_expression'):
                names.append(name)
            elif missing and (attributes.get('sqldefault') is not None
                              or attributes.get('dtype') in _GENERATED_KEY_DTYPES):
                names.append(name)
        return names

    @staticmethod
    def _update_returning(table):
        return [name for name, column in table.columns.items()
                if column.attributes.get('sql_value') is not None or column.attributes.get('generated_expression')]

    def _returning(self, table, names, capability):
        if not names or capability not in self.dialect.capabilities:
            return ''
        quote = self.dialect.quote_identifier
        projections = ','.join(f'{quote(table.columns[name].sqlname)} AS {quote(name)}' for name in names)
        return f' RETURNING {projections}'
