"""Live application tables, lazy query intent, and cached single-record reads.

Application objects execute through their owning SqlDatabase session. They do
not open connections, commit, or emulate legacy Bag/selection result objects.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from types import MappingProxyType

from .configuration import ConfigurationView
from .contracts import UnsupportedFeatureError


class RecordNotFoundError(LookupError):
    """No visible row matches the record selector."""


class RecordMultipleRowsError(LookupError):
    """A record selector matched more than one visible row."""


_SELECT_OPTIONS = frozenset({
    'order_by', 'limit', 'offset', 'exclude_draft', 'exclude_logical_deleted',
    'ignore_partition', 'for_update',
})
_ALIASES = {
    'excludeDraft': 'exclude_draft',
    'excludeLogicalDeleted': 'exclude_logical_deleted',
    'ignorePartition': 'ignore_partition',
}
_UNSUPPORTED = frozenset({
    'aggregateRows', '_aggregateRows', 'distinct', 'group_by', 'having',
    'relationDict', 'joinConditions', 'sqlContextName',
    'addPkeyColumn', 'ignoreTableOrderBy', 'subtable', 'bagFields',
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
    return '$"' + name.replace('"', '""') + '"'


class SqlColumn:
    """A stable live column handle linked to its owner's configuration tree."""

    def __init__(self, table, model):
        self.table = self.owner = table
        self.db = table.db
        self.model = model
        self.name = model.name
        self.fullname = f'{table.fullname}.{self.name}'
        collection = 'virtual_columns' if model.is_virtual else 'columns'
        fallback = (lambda: self.originalColumn.config) if model.alias_target is not None else None
        self.config = ConfigurationView(self.db.config, f'{table._config_prefix}.{collection}.{self.name}',
                                        fallback=fallback)

    @property
    def originalColumn(self):
        """Legacy-style link to an alias's target live column, if it is an alias."""
        if self.model.alias_target is None:
            return None
        table_name, column_name = self.model.alias_target
        return self.db.table(table_name).column(column_name)

    @property
    def relation_path(self):
        return self.model.relation_path


class SqlRelation:
    """A live relation whose target resolves lazily from the database registry."""

    def __init__(self, table, model):
        self.table = table
        self.db = table.db
        self.model = model
        self.name = model.name

    @property
    def target(self):
        return self.db.table(self.model.target)


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
        self.db._check_open()
        query = self.db.compiler.select(self.table.fullname, params=_copy(self._params),
                                        **_copy(self._options))
        unused = set(self._keyword_bindings) - set(query.input_parameters)
        if unused:
            raise UnsupportedFeatureError(
                f'Unknown query options or unused keyword bindings: {sorted(unused)}; '
                'use params for explicit parameter mappings')
        return query

    @property
    def sqltext(self):
        return self.compiled.sql

    def execute(self):
        return self.db.execute(self.compiled)

    def fetch(self):
        """Execute again and return ordinary dictionaries, without result caching."""
        return self.execute().rows

    def selection(self, *args, **kwargs):
        raise UnsupportedFeatureError('Selection and Bag output are outside this application profile')

    def count(self):
        raise UnsupportedFeatureError('The count terminal is not implemented; select an explicit SQL aggregate')


class SqlRecord:
    """Lazy exactly-one read; loaded data stays cached until explicit refresh."""

    def __init__(self, query):
        self.query = query
        self.table = query.table
        self.db = query.db
        self._result = None

    def _load(self):
        if self._result is None:
            rows = self.query.fetch()
            if not rows:
                raise RecordNotFoundError(f'No visible record in {self.table.fullname}')
            if len(rows) != 1:
                raise RecordMultipleRowsError(f'Multiple visible records in {self.table.fullname}')
            self._result = _copy(rows[0])
        return self._result

    def output(self, mode='dict'):
        if mode != 'dict':
            raise UnsupportedFeatureError(f'Unsupported record output: {mode!r}; supported: dict')
        return _copy(self._load())

    def refresh(self):
        """Discard the snapshot, reload in the current environment, and return self."""
        self._result = None
        self._load()
        return self


class SqlTable:
    """Session-bound application table with stable column/relation handles."""

    def __init__(self, db, model):
        self.db = db
        self.model = model
        self.fullname = model.key
        self._config_prefix = f'schemas.{model.schema}.tables.{model.name}'
        self.config = ConfigurationView(db.config, self._config_prefix)
        self.columns = MappingProxyType({name: SqlColumn(self, column)
                                         for name, column in model.columns.items()})
        self.relations = MappingProxyType({name: SqlRelation(self, relation)
                                           for name, relation in model.relations.items()})

    def column(self, name):
        try:
            return self.columns[name]
        except KeyError:
            raise ValueError(f'Unknown column {self.fullname}.{name}') from None

    def relation(self, name):
        try:
            return self.relations[name]
        except KeyError:
            raise ValueError(f'Unknown relation {self.fullname}.{name}') from None

    def query(self, columns='*', where=None, params=None, sqlparams=None, **options_or_bindings):
        self.db._check_open()
        incoming = dict(options_or_bindings)
        for alias, native in _ALIASES.items():
            if alias in incoming:
                if native in incoming:
                    raise ValueError(f'Conflicting query options: {alias} and {native}')
                incoming[native] = incoming.pop(alias)
        unsupported = incoming.keys() & _UNSUPPORTED
        if unsupported:
            raise UnsupportedFeatureError(f'Unsupported query options: {sorted(unsupported)}')
        options = {'columns': columns, 'where': where}
        options.update({key: incoming.pop(key) for key in list(incoming) if key in _SELECT_OPTIONS})
        bindings = _bindings(params, sqlparams, incoming)
        return SqlQuery(self, options, bindings, keyword_bindings=incoming)

    def _key_selector(self, pkey, params=None):
        names = self.model.pkey
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
        bindings = _bindings(params)
        conditions = []
        for index, (name, value) in enumerate(zip(names, values)):
            parameter = f'__record_key_{index}'
            while parameter in bindings:
                parameter = '_' + parameter
            bindings[parameter] = _copy(value)
            conditions.append(f'{_reference(name)} = :{parameter}')
        return ' AND '.join(conditions), bindings

    def record(self, pkey=None, where=None, params=None, sqlparams=None, mode=None, **options_or_bindings):
        self.db._check_open()
        if 'columns' in options_or_bindings:
            raise UnsupportedFeatureError('Record reads select the complete row; use query for custom projections')
        if 'limit' in options_or_bindings or 'offset' in options_or_bindings:
            raise UnsupportedFeatureError('Record reads cannot limit/offset away duplicate candidates')
        bindings = _bindings(params, sqlparams)
        if where is not None:
            if not isinstance(where, str) or not where.strip():
                raise ValueError('Record lookup needs a nonempty selector')
        elif pkey is not None:
            where, bindings = self._key_selector(pkey, bindings)
        else:
            raise ValueError('Record lookup requires a primary key or explicit where')
        result = SqlRecord(self.query(where=where, params=bindings, **options_or_bindings))
        return result.output(mode) if mode is not None else result

    def trigger_onInserting(self, record):
        """Override to validate/change the outgoing record in the shared session."""

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

    def _has_write_hooks(self, operation):
        names = ('trigger_onUpdating', 'trigger_onUpdated') if operation == 'update' else (
            'trigger_onDeleting', 'trigger_onDeleted')
        return any(getattr(type(self), name) is not getattr(SqlTable, name) for name in names)

    def _locked_record(self, where, params, ignore_partition):
        if not self.model.pkey:
            raise ValueError('Write hooks require a declared primary key')
        columns = ', '.join(_reference(name) for name, column in self.model.columns.items()
                            if not column.is_virtual)
        query = self.query(columns=columns, where=where, params=params, for_update=True, limit=2,
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

    def insert(self, values, returning='*', *, ignore_partition=False):
        with self.db._write_operation():
            if not isinstance(values, Mapping):
                raise TypeError('Insert values must be a mapping')
            record = _copy(dict(values))
            self.trigger_onInserting(record)
            result = self.db.execute(self.db.compiler.insert(
                self.fullname, record, returning, ignore_partition=ignore_partition))
            self._overlay_returned(record, result)
            self.trigger_onInserted(record)
            return result

    def update(self, values, where=None, params=None, returning='*', *, ignore_partition=False):
        with self.db._write_operation():
            if not isinstance(values, Mapping):
                raise TypeError('Update values must be a mapping')
            record = _copy(dict(values))
            if where is None:
                where, params = self._key_selector(record, params)
            # Validate the caller's write predicate and values before acquiring locks.
            compiled = self.db.compiler.update(
                self.fullname, record, where, params, returning, ignore_partition=ignore_partition)
            if not self._has_write_hooks('update'):
                return self.db.execute(compiled)
            old_record = self._locked_record(where, params, ignore_partition)
            key_where, key_params = self._key_selector(old_record)
            merged = _copy(old_record)
            merged.update(record)
            self.trigger_onUpdating(merged, old_record=_copy(old_record))
            result = self.db.execute(self.db.compiler.update(
                self.fullname, merged, key_where, key_params, returning,
                ignore_partition=ignore_partition))
            if result.rowcount != 1:
                raise RecordNotFoundError('Locked update did not affect exactly one record')
            self._overlay_returned(merged, result)
            self.trigger_onUpdated(merged, old_record=_copy(old_record))
            return result

    def delete(self, record_or_pkey=None, *, where=None, params=None, returning='*', ignore_partition=False):
        with self.db._write_operation():
            if where is None:
                if record_or_pkey is None:
                    raise ValueError('Delete requires a primary key, record, or explicit where')
                where, params = self._key_selector(record_or_pkey, params)
            compiled = self.db.compiler.delete(
                self.fullname, where, params, returning, ignore_partition=ignore_partition)
            if not self._has_write_hooks('delete'):
                return self.db.execute(compiled)
            record = self._locked_record(where, params, ignore_partition)
            key_where, key_params = self._key_selector(record)
            self.trigger_onDeleting(record)
            result = self.db.execute(self.db.compiler.delete(
                self.fullname, key_where, key_params, returning,
                ignore_partition=ignore_partition))
            if result.rowcount != 1:
                raise RecordNotFoundError('Locked delete did not affect exactly one record')
            self.trigger_onDeleted(record)
            return result

    def soft_delete(self, value, where, params=None, returning='*', *, ignore_partition=False):
        with self.db._write_operation():
            if value is None:
                raise ValueError('soft_delete requires a non-None tombstone value')
            field = self.db.compiler._tombstone(self.fullname)
            return self.update({field: value}, where, params, returning,
                               ignore_partition=ignore_partition)

    def restore(self, where, params=None, returning='*', *, ignore_partition=False):
        with self.db._write_operation():
            field = self.db.compiler._tombstone(self.fullname)
            return self.update({field: None}, where, params, returning,
                               ignore_partition=ignore_partition)
