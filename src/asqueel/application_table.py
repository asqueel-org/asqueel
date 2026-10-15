"""Live application tables, lazy query intent, and cached single-record reads.

Application objects execute through their owning SqlDatabase. They do
not open connections, commit, or emulate legacy Bag/selection result objects.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from copy import deepcopy
from types import MappingProxyType

from .configuration import ConfigurationView, _MISSING
from .contracts import UnsupportedFeatureError
from .object_tree import DbTableObj


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
    return '$"' + name.replace('"', '""') + '"'


def _model_config(model):
    """Keep the existing scoped read API, using only finalized model data."""
    def values(item):
        result = dict(item.attributes)
        if hasattr(item, 'dtype'):
            result['dtype'] = item.dtype
        for child in getattr(item, 'declarations', getattr(item, 'children', ())):
            key = (f'{child.kind}_{child.name}'
                   if child.kind in ('subtable', 'virtualRelation') else child.name)
            result[key] = values(child)
        if hasattr(item, 'options'):
            result['options'] = {key: values(option) for key, option in item.options.items()}
        if hasattr(item, 'columns'):
            for collection, virtual in (('columns', False), ('virtual_columns', True)):
                result[collection] = {name: values(column) for name, column in item.columns.items()
                                      if column.is_virtual == virtual}
        return result

    data = values(model)

    def read(path, default=_MISSING):
        current = data
        try:
            for key in path.split('.'):
                current = current[key]
        except (KeyError, TypeError):
            if default is not _MISSING:
                return default
            raise KeyError(path) from None
        return deepcopy(current)

    return read


class SqlColumn:
    """A stable live column handle backed by the completed structural model."""

    def __init__(self, table, model):
        self.table = self.owner = table
        self.db = table.db
        self.model = model
        self.name = model.name
        self.fullname = f'{table.fullname}.{self.name}'
        fallback = (lambda: self.originalColumn.config) if model.alias_target is not None else None
        self.config = ConfigurationView(_model_config(model), fallback=fallback)

    @property
    def validations(self):
        """Validation declarations from the translated column, without execution."""
        return self.model.validations

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
        return self._compile(self.db.compiler.select)

    def _compile(self, terminal):
        self.db._check_open()
        query = terminal(self.table.fullname, sqlparams=_copy(self._params),
                         **_copy(self._options))
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

    def selection(self, *args, **kwargs):
        raise UnsupportedFeatureError('Selection and Bag output are outside this application profile')

    def count(self):
        result = self.db.execute(self._compile(self.db.compiler.count))
        if isinstance(self.table.model, DbTableObj):
            # Legacy SqlQuery.count: grouped/distinct queries return rows;
            # only the ordinary COUNT(*) result carries gnr_row_count.
            if len(result.rows) == 1 and result.columns[0].name == 'gnr_row_count':
                return int(result.rows[0][0])
            return len(result.rows)
        return int(result.rows[0]['count'])


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
            self._result = _copy(dict(rows[0]))
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
    """Database-bound application table with stable column/relation handles."""

    def __init__(self, db, model):
        self.model = model
        if isinstance(model, DbTableObj):
            # As in legacy, construction precedes columns and global relations.
            # Structural access stays on the model, without SqlColumn/SqlRelation copies.
            self.fullname = model.fullname
            return
        self.db = db
        self.fullname = model.key
        self.config = ConfigurationView(_model_config(model))
        self.columns = MappingProxyType({name: SqlColumn(self, column)
                                         for name, column in model.columns.items()})
        self.relations = MappingProxyType({name: SqlRelation(self, relation)
                                           for name, relation in model.relations.items()})

    @property
    def db(self):
        if isinstance(self.model, DbTableObj):
            db = self.model._model._operational_db
            if db is None:
                raise UnsupportedFeatureError('Hierarchical table is not bound to a SqlDatabase')
            return db
        return self._db

    @db.setter
    def db(self, value):
        self._db = value

    def __getattr__(self, name):
        """Read missing members from the model, preserving their original binding."""
        # Bypass this fallback if model is not yet installed (e.g. during construction).
        model = object.__getattribute__(self, 'model')
        return getattr(model, name)

    def column(self, name):
        if isinstance(self.model, DbTableObj):
            return self.model.column(name)
        try:
            return self.columns[name]
        except KeyError:
            raise ValueError(f'Unknown column {self.fullname}.{name}') from None

    def relation(self, name):
        if isinstance(self.model, DbTableObj):
            raise UnsupportedFeatureError(
                'Hierarchical relations use table.relations and table.column("@relation.field")')
        try:
            return self.relations[name]
        except KeyError:
            raise ValueError(f'Unknown relation {self.fullname}.{name}') from None

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
            reference = '$' + name if isinstance(self.model, DbTableObj) else _reference(name)
            return f'CASE WHEN {reference} {condition} THEN {literal} ELSE NULL END'

        reasons = [reason(protection, 'IS NOT NULL', protection)] if protection else []
        columns = (self.model.virtual_columns.items() if isinstance(self.model, DbTableObj)
                   else ((name, column) for name, column in self.model.columns.items() if column.is_virtual))
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
        if isinstance(self.model, DbTableObj):
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
        bindings = _bindings(sqlparams)
        conditions = []
        for index, (name, value) in enumerate(zip(names, values)):
            parameter = f'__record_key_{index}'
            while parameter in bindings:
                parameter = '_' + parameter
            bindings[parameter] = _copy(value)
            conditions.append(f'{_reference(name)} = :{parameter}')
        return ' AND '.join(conditions), bindings

    def record(self, pkey=None, where=None, sqlparams=None, mode=None, **options_or_bindings):
        self.db._check_open()
        if isinstance(self.model, DbTableObj):
            raise UnsupportedFeatureError('Record reads on the hierarchical model are not connected yet')
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
        options_or_bindings.setdefault('bagFields', True)
        result = SqlRecord(self.query(where=where, sqlparams=bindings, **options_or_bindings))
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
