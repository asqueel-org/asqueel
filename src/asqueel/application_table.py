"""Live application tables and lazy query intent with the legacy fetch terminals.

Application objects execute through their owning SqlDatabase. They do
not open connections, commit, or emulate legacy selection result objects.
"""
from __future__ import annotations

import json
import sys
import warnings
from collections import OrderedDict
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime

from genro_bag import Bag
from genro_toolbox.uid import get_uuid

from .contracts import UnsupportedFeatureError, UnusedQueryParameterWarning, not_available, refused_property
from .hierarchical import HierarchicalHandler
from .table_crud import _INTEGER_DTYPES, CrudMixin
from .table_triggers import TriggersMixin


class RecordNotFoundError(LookupError):
    """No visible row matches the record selector."""


class RecordMultipleRowsError(LookupError):
    """A record selector matched more than one visible row."""


_SELECT_OPTIONS = frozenset({
    'order_by', 'limit', 'offset', 'exclude_draft', 'exclude_logical_deleted',
    'ignore_partition', 'for_update', 'distinct', 'group_by', 'having', 'bagFields',
})
_ALIASES = {
    'excludeDraft': 'exclude_draft',
    'excludeLogicalDeleted': 'exclude_logical_deleted',
    'ignorePartition': 'ignore_partition',
}
_UNSUPPORTED = frozenset({
    'aggregateRows', '_aggregateRows',
    'relationDict', 'joinConditions', 'sqlContextName',
    'addPkeyColumn', 'ignoreTableOrderBy', 'subtable',
    '_storename', 'storename', 'locale', 'mode', 'checkPermissions', 'aliasPrefix',
    'lazy', 'eager', 'virtual_columns', 'ignoreMissing', 'ignoreDuplicate',
})


def _copy(value):
    try:
        return deepcopy(value)
    except Exception as error:
        raise ValueError('Application query and record values must support deepcopy') from error


def _bindings(*sources):
    result = {}
    for source in sources:
        if source is None:
            continue
        if not isinstance(source, Mapping):
            raise TypeError('Query parameters must be mappings')
        duplicates = result.keys() & source.keys()
        if duplicates:
            raise ValueError(f'Duplicate parameter declarations: {sorted(duplicates)}')
        result.update(_copy(dict(source)))
    return result


def _reference(name):
    return '$' + name


class SqlQuery:
    """Query intent compiled once, on first use; :env_* values are read at every execution."""

    @property
    def setJoinCondition(self):
        raise not_available('setJoinCondition')

    def __init__(self, table, options, params, keyword_bindings=()):
        self.table = table
        self.db = table.db
        self._options = _copy(dict(options))
        self._params = _copy(dict(params))
        self._keyword_bindings = tuple(keyword_bindings)
        self._compiled = None
        self._compiled_first_row = None

    @property
    def compiled(self):
        """The compiled query, built on first access and kept: its SQL text is the one of that compilation."""
        if self._compiled is None:
            self._compiled = self._compile(self.db.compiler.select)
        return self._compiled

    def _compile(self, terminal, options=None):
        self.db._check_open()
        query = terminal(self.table.fullname, sqlparams=_copy(self._params),
                         **_copy(self._options if options is None else options))
        unused = sorted(set(self._keyword_bindings) - set(query.input_parameters))
        if unused:
            # Point the warning at the caller's line, outside the asqueel package.
            frame, stacklevel = sys._getframe(1), 2
            while frame.f_back is not None and frame.f_globals.get('__name__', '').startswith('asqueel.'):
                frame, stacklevel = frame.f_back, stacklevel + 1
            for name in unused:
                warnings.warn(UnusedQueryParameterWarning(
                    f"query keyword {name!r} is not used by the query; "
                    f"its parameters are: {', '.join(query.input_parameters)}"), stacklevel=stacklevel)
        return query

    @property
    def sqltext(self):
        return self.compiled.sql

    @property
    def sqlparams(self):
        """The query parameters; the :env_* values are read at execution, so they are not listed."""
        environment = {'env_' + key for key in self.compiled.environment_keys}
        return {name: value for name, value in self.compiled.params.items() if name not in environment}

    def test(self):
        """``(sqltext, sqlparams)`` of the compiled query, as legacy."""
        return self.sqltext, self.sqlparams

    def execute(self):
        return self.db.execute(self.compiled)

    def fetch(self):
        """Execute again and return mutable Toolbox NamedList rows, without caching."""
        return self.handleBagColumns(self._fetchall(self.compiled), self.compiled)

    def _fetchall(self, compiled):
        cursor = self.db.execute(compiled)
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def handleBagColumns(self, rows, compiled):
        """Legacy handleBagColumns: a #BAG value becomes a Bag, #BAGCOLS spreads its leaves into columns."""
        for row in rows:
            for field, separateCols in compiled.evaluateBagColumns:
                value = Bag() if row[field] is None else Bag.from_xml(row[field])
                if separateCols:
                    for path, leaf in value.get_leaves():
                        row[f'{field}_{path.replace(".", "_")}'] = leaf
                    row[field] = None
                else:
                    row[field] = value
        return rows

    def cursor(self):
        """Execute the query and return its open cursor; the caller closes it."""
        return self.db.cursor(self.compiled)

    def servercursor(self):
        """A named server-side cursor on PostgreSQL; a normal cursor on SQLite (legacy gnrsqlite)."""
        return self.db.cursor(self.compiled, cursorname='asqueel_' + get_uuid())

    def serverfetch(self, arraysize=30):
        """``(cursor, generator)``: the generator yields lists of at most ``arraysize`` rows."""
        cursor = self.servercursor()
        cursor.arraysize = arraysize
        return cursor, self._cursorGenerator(cursor)

    def iterfetch(self, arraysize=30):
        """Yield the rows in lists of at most ``arraysize``, from a server-side cursor."""
        yield from self.serverfetch(arraysize=arraysize)[1]

    def _cursorGenerator(self, cursor):
        """Legacy _cursorGenerator: chunks until the cursor is exhausted, the last one empty."""
        try:
            rows = True
            while rows:
                rows = cursor.fetchmany()
                yield self.handleBagColumns(rows, self.compiled)
        finally:
            cursor.close()

    def fetchPkeys(self):
        """The primary-key values of the rows, in query order."""
        pkey = self.table.model.pkey
        return [row[pkey] for row in self.fetch()]

    def fetchAsJson(self, key=None):
        """The rows as a JSON array; datetimes in ISO format, other values through ``str``."""
        def default(value):
            return value.isoformat() if isinstance(value, datetime) else str(value)
        return json.dumps([dict(row) for row in self.fetch()], default=default)

    def fetchAsDict(self, key=None, ordered=False, pkeyOnly=False):
        """The rows keyed by ``key`` (default the pkey); ``pkeyOnly`` keeps only the pkey as value."""
        key = key or self.table.model.pkey
        factory = OrderedDict if ordered else dict
        if pkeyOnly:
            pkey = self.table.model.pkey
            return factory((row[key], row[pkey]) for row in self.fetch())
        return factory((row[key], row) for row in self.fetch())

    def fetchAsBag(self, key=None):
        """A Bag with one node per row, labelled by ``key`` and sorted by it, the row as attributes."""
        key = key or self.table.model.pkey
        result = Bag()
        for row in sorted(self.fetch(), key=lambda row: row[key]):
            result.set_item(row[key], None, _attributes=dict(row))
        return result

    def fetchGrouped(self, key=None, asBag=False, ordered=False):
        """Lists of rows grouped by ``key`` (default the pkey), in a dict, OrderedDict or Bag."""
        key = key or self.table.model.pkey
        result = Bag() if asBag else OrderedDict() if ordered else {}
        for row in self.fetch():
            if row[key] in result:
                result[row[key]].append(row)
            else:
                result[row[key]] = [row]
        return result

    def fetchRecord(self, ignoreMissing=False):
        """The single row of the query; with an explicit order_by, the first row.

        No row raises RecordNotFoundError, or returns None with ``ignoreMissing``;
        several rows raise RecordMultipleRowsError.
        """
        if self._options.get('order_by'):
            if self._compiled_first_row is None:
                options = dict(_copy(self._options), limit=1)
                self._compiled_first_row = self._compile(self.db.compiler.select, options)
            compiled = self._compiled_first_row
            rows = self.handleBagColumns(self._fetchall(compiled), compiled)
        else:
            rows = self.fetch()
        if not rows:
            if ignoreMissing:
                return None
            raise RecordNotFoundError(f'No visible record in {self.table.fullname}')
        if len(rows) > 1:
            raise RecordMultipleRowsError(f'Multiple visible records in {self.table.fullname}')
        return rows[0]

    def sql_delete(self):
        """DELETE the rows this query selects, without triggers; returns the row count."""
        table = self.table.model
        plan = self._key_plan(table)
        compiled = self.db.write_compiler.delete_selection(table, plan, self.db.environment.snapshot())
        return self._rowcount(compiled)

    def _rowcount(self, compiled):
        cursor = self.db.execute(compiled)
        rowcount: int = cursor.rowcount
        cursor.close()
        return rowcount

    def sql_update(self, values):
        """UPDATE the rows this query selects with ``values``, without triggers; returns the row count."""
        table = self.table.model
        plan = self._key_plan(table)
        compiled = self.db.write_compiler.update_selection(table, plan, values, self.db.environment.snapshot())
        return self._rowcount(compiled)

    def delete(self):
        """Delete the selected rows one by one through the write cycle; returns the rows."""
        table = self.table
        pkey = table.model.pkey
        rows = self._rows_to_write('delete')
        for row in rows:
            # A key string is reread: a row already removed by a cascade is skipped.
            table.delete(str(row[pkey]) if pkey in row else table.pkeyValue(row))
        return rows

    def update(self, updater):
        """Update the selected rows one by one through the write cycle; returns their pkeys.

        ``updater`` is a dict merged into each row, or a callable changing the row in place.
        """
        table = self.table
        pkey = table.model.pkey
        pkeys = []
        for old_record in self._rows_to_write('update'):
            record = _copy(old_record)
            if callable(updater):
                updater(record)
            else:
                record.update(updater)
            table.update(record, old_record=old_record)
            pkeys.append(record[pkey] if pkey in record else table.pkeyValue(record))
        return pkeys

    def _rows_to_write(self, terminal):
        """The selected rows with every physical column, locked, as dicts."""
        options = _copy(self._options)
        grouping = [name for name in ('group_by', 'having') if options.get(name)]
        if grouping:
            raise UnsupportedFeatureError(f'{", ".join(grouping)} is valid only in a SELECT, not in {terminal}')
        options['columns'] = ','.join(_reference(name) for name in self.table.model.columns)
        options['bagFields'] = True
        options['for_update'] = options.get('for_update') or True
        compiled = self._compile(self.db.compiler.select, options)
        return [dict(row) for row in self.handleBagColumns(self._fetchall(compiled), compiled)]

    def _key_plan(self, table):
        """The query's SELECT with the same filters, order and limit, reduced to the key."""
        options = _copy(self._options)
        grouping = [name for name in ('group_by', 'having') if options.get(name)]
        if grouping:
            raise UnsupportedFeatureError(f'{", ".join(grouping)} is valid only in a SELECT, not in sql_update or sql_delete')
        options['columns'] = ','.join(_reference(name) for name in self.db.write_compiler.pkeys(table))
        options.pop('addPkeyColumn', None)
        options.pop('bagFields', None)
        return self._compile(self.db.compiler.plan_select, options)

    def selection(self, *args, **kwargs):
        raise UnsupportedFeatureError('selection(): Selection and Bag output are not available in this release')

    def count(self):
        cursor = self.db.execute(self._compile(self.db.compiler.count))
        rows = cursor.fetchall()
        name = cursor.description[0][0]
        cursor.close()
        # Legacy count returns rows for grouped/distinct queries.
        if len(rows) == 1 and name == 'gnr_row_count':
            return int(rows[0][0])
        return len(rows)


class SqlTable(CrudMixin, TriggersMixin):
    """Database-bound application table with stable column/relation handles."""

    def __init__(self, db, model):
        self.model = model
        self.fullname = model.fullname
        if model.attributes.get('x_legacy_hierarchical'):
            self.hierarchicalHandler = HierarchicalHandler(self)

    @property
    def db(self):
        db = self.model._model._operational_db
        if db is None:
            raise UnsupportedFeatureError('Table is not bound to a SqlDatabase')
        return db

    def __getattr__(self, name):
        """Read missing members from the model, preserving their original binding."""
        # Bypass this fallback if model is not yet installed (e.g. during construction).
        model = object.__getattribute__(self, 'model')
        return getattr(model, name)

    def column(self, name):
        return self.model.column(name)

    def sql_formula___protecting_reasons(self, attr):
        """Legacy sysFields formula; this describes reasons, not write checks."""
        attributes = self.model.attributes
        protection = attributes.get('protectionColumn')
        return self._sql_reasons('__protected_by_', protection)

    def sql_formula___invalid_reasons(self, attr):
        """Legacy sysFields formula, including NULL when no rules are declared."""
        return self._sql_reasons('__invalid_by_')

    def _sql_reasons(self, prefix, protection=None):
        def reason(name, condition, label):
            literal = "'" + label.replace("'", "''") + "'"
            reference = '$' + name
            return f'CASE WHEN {reference} {condition} THEN {literal} ELSE NULL END'

        reasons = [reason(protection, 'IS NOT NULL', protection)] if protection else []
        columns = self.model.virtual_columns.items()
        reasons.extend(reason(name, 'IS TRUE', name[len(prefix):])
                       for name, column in columns if name.startswith(prefix))
        return self.db.adapter.string_join(reasons, ',') if reasons else 'NULL'

    readColumns = refused_property('readColumns')
    countRecords = refused_property('countRecords')
    recordAs = refused_property('recordAs')
    cachedRecord = refused_property('cachedRecord')
    sqlWhereFromBag = refused_property('sqlWhereFromBag')
    whereTranslator = refused_property('whereTranslator')

    def query(self, columns='*', where=None, sqlparams=None, **options_or_bindings):
        self.db._check_open()
        if columns is None or columns == '':
            raise not_available(f'columns={columns!r}')
        incoming = dict(options_or_bindings)
        for alias, native in _ALIASES.items():
            if alias in incoming:
                if native in incoming:
                    raise ValueError(f'Conflicting query options: {alias} and {native}')
                incoming[native] = incoming.pop(alias)
        select_options = _SELECT_OPTIONS
        unsupported_options = _UNSUPPORTED
        select_options = select_options | {'addPkeyColumn'}
        unsupported_options = unsupported_options - {'addPkeyColumn'}
        join_conditions = sorted(key for key in incoming if key.startswith('jc_'))
        if join_conditions:
            raise not_available(f'join condition keyword {join_conditions[0]}')
        unsupported = incoming.keys() & unsupported_options
        if unsupported:
            name = sorted(unsupported)[0]
            raise UnsupportedFeatureError(f'query option {name!r} is not available in this release')
        options = {'columns': columns, 'where': where}
        options.update({key: incoming.pop(key) for key in list(incoming) if key in select_options})
        if options.get('for_update') and (options.get('distinct') or options.get('group_by')):
            raise UnsupportedFeatureError('for_update is incompatible with distinct or group_by')
        bindings = _bindings(sqlparams, incoming)
        return SqlQuery(self, options, bindings, keyword_bindings=incoming)

    def _key_selector(self, pkey):
        names = self.model._model.physical_columns(self.model, self.model.pkey) if self.model.pkey else ()
        if not names:
            raise ValueError(f'{self.fullname} has no declared primary key')
        values = self.db.write_compiler.key_values(self.model, pkey)
        if any(value is None for value in values):
            raise ValueError('Primary-key values must not be None')
        bindings = {}
        conditions = []
        for index, (name, value) in enumerate(zip(names, values)):
            parameter = f'__record_key_{index}'
            bindings[parameter] = _copy(value)
            conditions.append(f'{_reference(name)} = :{parameter}')
        return ' AND '.join(conditions), bindings

    def record(self, *args, **kwargs):
        raise UnsupportedFeatureError('record is not available in this release; use query(...).fetchRecord()')

    @property
    def currentTrigger(self):
        """Current write operation; ``parent`` is the operation that caused it."""
        return getattr(self.db, 'currentTrigger', None)

    def sql_insert(self, record):
        """Insert without triggers (legacy raw_insert); a list runs one executemany per column set.

        Missing keys are assigned first (checkPkey); in a list each further
        integer key is the next integer. A key the database generates is left out.
        """
        writer, snapshot = self.db.write_compiler, self.db.environment.snapshot()
        self._assign_keys(record if isinstance(record, list) else [record])
        if isinstance(record, list):
            for compiled, params in writer.insert_many(self.model, record, snapshot):
                self.db.executemany(compiled, params).close()
            return record
        cursor = self.db.execute(writer.insert(self.model, record, snapshot))
        rows = cursor.fetchall() if cursor.description is not None else []
        cursor.close()
        if rows:
            record.update(dict(rows[0]))
        return record

    def _assign_keys(self, records):
        pkey = self.model.pkey
        if not pkey:
            return
        if self._pkey_from_database():
            return
        column = self.model.columns.get(pkey)
        integer = column is not None and column.dtype in _INTEGER_DTYPES
        next_integer = None
        for record in records:
            if integer and next_integer is not None and record.get(pkey) in (None, ''):
                record[pkey] = next_integer
            else:
                self.checkPkey(record)
            if integer and record.get(pkey) is not None:
                next_integer = max(next_integer or 0, record[pkey] + 1)

    def sql_update(self, record, old_record=None, pkey=None):
        """Update without triggers (legacy raw_update); the key comes from old_record, pkey or record."""
        self.db.execute(self.db.write_compiler.update(
            self.model, record, self.db.environment.snapshot(), pkey=pkey, old_record=old_record)).close()

    def sql_delete(self, record):
        """Delete without triggers or related actions (legacy raw_delete)."""
        self.db.execute(self.db.write_compiler.delete(self.model, record, self.db.environment.snapshot())).close()
