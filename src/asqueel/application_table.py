"""Live application tables, lazy query intent, and cached single-record reads.

Application objects execute through their owning SqlDatabase. They do
not open connections, commit, or emulate legacy Bag/selection result objects.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from copy import deepcopy

from .contracts import UnsupportedFeatureError


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
    """Detached query intent; every terminal compiles in the current environment."""

    def __init__(self, table, options, params, keyword_bindings=()):
        self.table = table
        self.db = table.db
        self._options = _copy(dict(options))
        self._params = _copy(dict(params))
        self._keyword_bindings = tuple(keyword_bindings)

    @property
    def compiled(self):
        return self._compile(self.db.compiler.select)

    def _compile(self, terminal, options=None):
        self.db._check_open()
        query = terminal(self.table.fullname, sqlparams=_copy(self._params),
                         **_copy(self._options if options is None else options))
        unused = set(self._keyword_bindings) - set(query.input_parameters)
        if unused:
            raise UnsupportedFeatureError(
                f'Unknown query options or unused keyword bindings: {sorted(unused)}; '
                'use sqlparams for explicit parameter mappings')
        return query

    @property
    def sqltext(self):
        return self.compiled.sql

    def execute(self):
        return self.db.execute(self.compiled)

    def fetch(self):
        """Execute again and return mutable Toolbox NamedList rows, without caching."""
        return self.execute().rows

    def sql_delete(self):
        """DELETE the rows this query selects, without triggers; returns the row count."""
        table = self.table.model
        plan = self._key_plan(table)
        compiled = self.db.write_compiler.delete_selection(table, plan, self.db.environment.snapshot())
        return self.db.execute(compiled).rowcount

    def sql_update(self, values):
        """UPDATE the rows this query selects with ``values``, without triggers; returns the row count."""
        table = self.table.model
        plan = self._key_plan(table)
        compiled = self.db.write_compiler.update_selection(table, plan, values, self.db.environment.snapshot())
        return self.db.execute(compiled).rowcount

    def _key_plan(self, table):
        """The query's SELECT with the same filters, order and limit, reduced to the key."""
        options = _copy(self._options)
        options['columns'] = ','.join(_reference(name) for name in self.db.write_compiler.pkeys(table))
        options.pop('addPkeyColumn', None)
        options.pop('bagFields', None)
        return self._compile(self.db.compiler.plan_select, options)

    def selection(self, *args, **kwargs):
        raise UnsupportedFeatureError('Selection and Bag output are outside this application profile')

    def count(self):
        result = self.db.execute(self._compile(self.db.compiler.count))
        # Legacy count returns rows for grouped/distinct queries.
        if len(result.rows) == 1 and result.columns[0].name == 'gnr_row_count':
            return int(result.rows[0][0])
        return len(result.rows)


class SqlRecord:
    """Lazy exactly-one read; loaded data stays cached until explicit refresh."""

    def __init__(self, query, *, ignoreMissing=False):
        self.ignoreMissing = ignoreMissing
        self.query = query
        self.table = query.table
        self.db = query.db
        self._result = None

    def _load(self):
        if self._result is None:
            rows = self.query.fetch()
            if not rows and self.ignoreMissing:
                self._result = {}
                return self._result
            if not rows:
                raise RecordNotFoundError(f'No visible record in {self.table.fullname}')
            if len(rows) != 1:
                raise RecordMultipleRowsError(f'Multiple visible records in {self.table.fullname}')
            self._result = _copy(dict(rows[0]))
        return self._result

    def output(self, mode='dict'):
        if mode == 'dict':
            return _copy(self._load())
        if mode == 'record':
            from genro_bag import Bag
            result = Bag()
            for name, value in _copy(self._load()).items():
                column = self.table.model.column(name)
                result.set_item(name, Bag(value) if column.dtype == 'X' else value,
                                _attributes=dict(column.attributes, dtype=column.dtype))
            return result
        raise UnsupportedFeatureError(f'Unsupported record output: {mode!r}; supported: dict, record')

    def refresh(self):
        """Discard the snapshot, reload in the current environment, and return self."""
        self._result = None
        self._load()
        return self


class SqlTable:
    """Database-bound application table with stable column/relation handles."""

    def __init__(self, db, model):
        self.model = model
        self.fullname = model.fullname

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
        protection = attributes.get('protectionColumn', attributes.get('x_legacy_protectionColumn'))
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
        return self.db.dialect.concat_non_null(reasons, ',') if reasons else 'NULL'

    def query(self, columns='*', where=None, sqlparams=None, **options_or_bindings):
        self.db._check_open()
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
        unsupported = incoming.keys() & unsupported_options
        if unsupported:
            raise UnsupportedFeatureError(f'Unsupported query options: {sorted(unsupported)}')
        options = {'columns': columns, 'where': where}
        options.update({key: incoming.pop(key) for key in list(incoming) if key in select_options})
        bindings = _bindings(sqlparams, incoming)
        return SqlQuery(self, options, bindings, keyword_bindings=incoming)

    def _key_selector(self, pkey, sqlparams=None):
        names = self.model._model.physical_columns(self.model, self.model.pkey) if self.model.pkey else ()
        if not names:
            raise ValueError(f'{self.fullname} has no declared primary key')
        if isinstance(pkey, Mapping):
            missing = set(names) - pkey.keys()
            if missing:
                raise ValueError(f'Incomplete primary key: {sorted(missing)}')
            values = [pkey[name] for name in names]
        elif len(names) == 1:
            values = [pkey]
        elif isinstance(pkey, (tuple, list)) and len(pkey) == len(names):
            values = list(pkey)
        else:
            raise ValueError('Composite primary keys require a complete mapping or ordered sequence')
        if any(value is None for value in values):
            raise ValueError('Primary-key values must not be None')
        bindings = _bindings(sqlparams)
        conditions = []
        for index, (name, value) in enumerate(zip(names, values)):
            parameter = f'__record_key_{index}'
            while parameter in bindings:
                parameter = '_' + parameter
            bindings[parameter] = _copy(value)
            conditions.append(f'{_reference(name)} = :{parameter}')
        return ' AND '.join(conditions), bindings

    def record(self, pkey=None, where=None, sqlparams=None, mode=None, *, ignoreMissing=False, **options_or_bindings):
        self.db._check_open()
        if 'columns' in options_or_bindings:
            raise UnsupportedFeatureError('Record reads select the complete row; use query for custom projections')
        if 'limit' in options_or_bindings or 'offset' in options_or_bindings:
            raise UnsupportedFeatureError('Record reads cannot limit/offset away duplicate candidates')
        bindings = _bindings(sqlparams)
        if where is not None:
            if not isinstance(where, str) or not where.strip():
                raise ValueError('Record lookup needs a nonempty selector')
        elif pkey is not None:
            where, bindings = self._key_selector(pkey, bindings)
        else:
            raise ValueError('Record lookup requires a primary key or explicit where')
        # Legacy compiledRecordQuery includes physical X fields by default,
        # unlike a normal SELECT wildcard. Preserve the complete record here.
        # compiledRecordQuery selects the record without the query visibility filters.
        for alias, native, value in [('excludeDraft', 'exclude_draft', False),
                                     ('excludeLogicalDeleted', 'exclude_logical_deleted', False),
                                     ('ignorePartition', 'ignore_partition', True)]:
            if alias not in options_or_bindings and native not in options_or_bindings:
                options_or_bindings[native] = value
        options_or_bindings.setdefault('bagFields', True)
        bag_fields = options_or_bindings['bagFields'] or options_or_bindings.get('for_update', False)
        columns = ','.join('$' + name for name, column in self.model.columns.items()
                           if bag_fields or column.dtype != 'X')
        result = SqlRecord(self.query(columns=columns, where=where, sqlparams=bindings, **options_or_bindings),
                           ignoreMissing=ignoreMissing)
        return result.output(mode) if mode is not None else result

    def trigger_onInserting(self, record):
        """Override to validate/change the outgoing record in the selected connection."""

    def trigger_onInserted(self, record):
        """Override to react to input values overlaid with available returned fields."""

    def trigger_onUpdating(self, record, old_record=None):
        """Override to prepare a complete record using its locked old snapshot."""

    def trigger_onUpdated(self, record, old_record=None):
        """Override to react after updating within the same unit of work."""

    def trigger_onDeleting(self, record):
        """Override to validate a locked record before physical deletion."""

    def trigger_onDeleted(self, record):
        """Override to react after physical deletion."""

    @property
    def currentTrigger(self):
        """Current write operation with ``parent`` and zero-based ``level``."""
        return getattr(self.db, 'currentTrigger', None)

    @contextmanager
    def _trigger_operation(self, event, record=None, old_record=None):
        operation = getattr(self.db, '_trigger_operation', None)
        if operation is None:
            yield None
            return
        with operation(event, self, record=record, old_record=old_record) as item:
            yield item

    def _locked_record(self, where, sqlparams, ignore_partition):
        if not self.model.pkey:
            raise ValueError('Ordinary update/delete require a declared primary key')
        columns = ', '.join(_reference(name) for name, column in self.model.columns.items()
                            if not column.is_virtual)
        query = self.query(columns=columns, where=where, sqlparams=sqlparams, for_update=True, limit=2,
                           exclude_draft=False, exclude_logical_deleted=False,
                           ignore_partition=ignore_partition)
        return SqlRecord(query).output()

    def _overlay_returned(self, record, result):
        if result.rows:
            sources = {column.identity or f'{self.fullname}.{name}': name
                       for name, column in self.model.columns.items()}
            returned = result.rows[0]
            for column in result.columns:
                name = sources.get(column.source)
                if name is not None and column.name in returned:
                    record[name] = _copy(returned[column.name])

    def sql_insert(self, record):
        """raw_insert without triggers; a list runs one executemany per column set."""
        writer, snapshot = self.db.write_compiler, self.db.environment.snapshot()
        if isinstance(record, list):
            for compiled, params in writer.insert_many(self.model, record, snapshot):
                self.db.executemany(compiled, params)
            return record
        result = self.db.execute(writer.insert(self.model, record, snapshot))
        if result.rows:
            record.update(dict(result.rows[0]))
        return record

    def sql_update(self, record, old_record=None, pkey=None):
        """raw_update without triggers; the key comes from old_record, pkey or record."""
        self.db.execute(self.db.write_compiler.update(
            self.model, record, self.db.environment.snapshot(), pkey=pkey, old_record=old_record))

    def sql_delete(self, record):
        """raw_delete without triggers or related actions."""
        self.db.execute(self.db.write_compiler.delete(self.model, record, self.db.environment.snapshot()))

    def insert(self, values, returning='*', *, ignore_partition=False):
        return self.db.insert(self, values, returning, ignore_partition=ignore_partition)

    def raw_insert(self, values, returning='*', *, ignore_partition=False):
        return self.db.raw_insert(self, values, returning, ignore_partition=ignore_partition)

    def update(self, values, where=None, sqlparams=None, returning='*', *, ignore_partition=False):
        return self.db.update(self, values, where, sqlparams, returning, ignore_partition=ignore_partition)

    def raw_update(self, values, where=None, sqlparams=None, returning='*', *, ignore_partition=False):
        return self.db.raw_update(self, values, where, sqlparams, returning, ignore_partition=ignore_partition)

    def delete(self, record_or_pkey=None, *, where=None, sqlparams=None, returning='*', ignore_partition=False):
        return self.db.delete(self, record_or_pkey, where=where, sqlparams=sqlparams,
                              returning=returning, ignore_partition=ignore_partition)

    def raw_delete(self, record_or_pkey=None, *, where=None, sqlparams=None, returning='*', ignore_partition=False):
        return self.db.raw_delete(self, record_or_pkey, where=where, sqlparams=sqlparams,
                                  returning=returning, ignore_partition=ignore_partition)

    def soft_delete(self, value, where, sqlparams=None, returning='*', *, ignore_partition=False):
        with self.db._write_operation():
            if value is None:
                raise ValueError('soft_delete requires a non-None tombstone value')
            field = self.db.compiler._tombstone(self.fullname)
            return self.update({field: value}, where, sqlparams, returning,
                               ignore_partition=ignore_partition)

    def restore(self, where, sqlparams=None, returning='*', *, ignore_partition=False):
        with self.db._write_operation():
            field = self.db.compiler._tombstone(self.fullname)
            return self.update({field: None}, where, sqlparams, returning,
                               ignore_partition=ignore_partition)
