"""Base adapter, after legacy ``_gnrbaseadapter.SqlDbAdapter``.

The database is the abstraction; the adapter adapts it to one implementation:
SQL text, quoting, capabilities, connection, cursor and value conversion.
Backend modules override what differs.
"""
from __future__ import annotations

from datetime import date
import re

from genro_toolbox import NamedList

from ..contracts import (CompiledQuery, EnvironmentBinding, QueryResult, ResultColumn,
                         UnsupportedFeatureError)


SQL_PARAMS = re.compile(r'(?<!:):(?!:)(\S\w*)(\W|$)')
ENV_PARAMS = re.compile(r':env_(\S\w*)(\W|$)')


def prepare_arguments(sql, sqlargs, snapshot):
    """The value preparation from legacy execute, without connection/store lifecycle."""
    keys = {key for key, _ in ENV_PARAMS.findall(sql)}
    params = {'env_' + key: snapshot.get(key) for key in keys}
    if 'env_workdate' in params:
        params['env_workdate'] = params['env_workdate'] or date.today()
    if snapshot.get('storename'):
        params['env_storename'] = snapshot['storename']
    keys = {key for key in keys if 'env_' + key not in (sqlargs or {})}
    params.update(sqlargs or {})
    for key, value in list(params.items()):
        if isinstance(value, bytes):
            value = value.decode('utf-8')
            params[key] = value
        if isinstance(value, str) and value.startswith((r'\$', r'\@')):
            params[key] = value[1:]
    return params, keys


def query_result(columns, names, cursor) -> QueryResult:
    """One column index per result set, shared by its mutable rows."""
    if names is None:
        if columns:
            raise ValueError('Compiled result columns supplied for a statement without a result set')
        return QueryResult([], cursor.rowcount, columns)
    if len(set(names)) != len(names):
        raise ValueError('Result columns must have unique names; use explicit aliases')
    if columns and [column.name for column in columns] != names:
        raise ValueError('Compiled result columns do not match cursor column names and order')
    index = {name: position for position, name in enumerate(names)}
    rows = [NamedList(index, row) for row in cursor.fetchall()]
    return QueryResult(rows, cursor.rowcount, columns or tuple(ResultColumn(name) for name in names))


#: Legacy ageAtDate time units, in seconds.
_TIME_UNITS = dict(year=365 * 24 * 60 * 60, month=int(365 * 24 * 60 * 60 / 12), week=7 * 24 * 60 * 60,
                   day=24 * 60 * 60, hour=60 * 60, minute=60, second=1)


def sql_literal(text):
    return "'" + text.replace("'", "''") + "'"


def mask_bounds(mode):
    """Visible characters at start and end of an 'N-M' mask_field_sql mode."""
    parts = mode.split('-')
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError(f"mask_field_sql: unknown mode {mode!r}; use 'email', 'creditcard', 'phone' or 'N-M'")
    return int(parts[0]), int(parts[1])


class SqlDbAdapter:
    """Common SQL; each backend adapter overrides its own peculiarities."""

    dialect = ''
    binding = ''
    capabilities: frozenset[str] = frozenset()

    def __init__(self, dbroot, **options):
        self.dbroot = dbroot
        capabilities = options.pop('capabilities', None)
        if options:
            raise ValueError(f'Unknown adapter options: {sorted(options)}')
        if capabilities is not None:
            unknown = set(capabilities) - type(self).capabilities
            if unknown:
                raise ValueError(f'Unknown {self.dialect} capabilities: {sorted(unknown)}')
            self.capabilities = frozenset(capabilities)

    def _require(self, capability):
        if capability not in self.capabilities:
            raise UnsupportedFeatureError(f'{self.dialect}: unsupported capability {capability}')

    def asTranslator(self, as_: str) -> str:
        """Legacy asTranslator: quote result aliases; let the DB handle length.

        A generated expression alias can exceed PostgreSQL's identifier length,
        as in the existing priced_rows_pct scalar subquery. Physical identifiers
        keep their separate adaptSqlName validation.
        """
        return '"' + as_.replace('"', '""') + '"'

    def adaptSqlName(self, name: str) -> str:
        if not isinstance(name, str) or not name or '\x00' in name:
            raise ValueError('SQL identifiers must be nonempty strings without NUL')
        return '"' + name.replace('"', '""') + '"'

    def empty_collection(self, negated: bool) -> str:
        """Operand-free replacement of ``IN`` / ``NOT IN`` for an empty collection."""
        return "<> ALL('{}')" if negated else "= ANY('{}')"

    def string_join(self, expressions: list[str], separator: str) -> str:
        """Legacy string_join: skip NULL terms, keep empty strings."""
        literal = "'" + separator.replace("'", "''") + "'"
        return f"array_to_string(ARRAY[{', '.join(expressions)}]::text[], {literal})"

    def concat_template(self, parts: list[tuple[str, bool]]) -> str:
        """#TEMPLATE: literal text and expressions; a NULL expression gives ''."""
        terms = [f"'{text.replace(chr(39), chr(39) * 2)}'" if literal else text
                 for text, literal in parts]
        return f"concat({', '.join(terms)})" if terms else "''"

    def join_sql_subquery(self, sql, alias):
        """Concatenate an ordered row source, preserving empty-value positions."""
        row = self.adaptSqlName(alias)
        return (f"(SELECT COALESCE(string_agg({row}.value, {row}.separator), '') "
                f'FROM ({sql}) AS {row})')

    def compileSql(self, maintable, columns, distinct='', joins=None, where=None,
                   group_by=None, having=None, order_by=None, limit=None, offset=None,
                   for_update=False, maintable_as='t0'):
        """Legacy compileSql over resolved strings."""
        self._require('select')
        if not columns.strip():
            raise ValueError('SELECT needs result columns')
        for name, value in (('limit', limit), ('offset', offset)):
            if value and (type(value) is not int or value < 0):
                raise ValueError(f'{name} must be a nonnegative integer')
            if value:
                self._require(name)
        if for_update:
            self._require('for_update')
        result = [f'SELECT {distinct}{columns}',
                  f' FROM {maintable} AS {self.adaptSqlName(maintable_as)}']
        for join in joins or ():
            self._require('left_join')
            result.append(f'       {join}')
        for name, value in (('WHERE', where), ('GROUP BY', group_by), ('HAVING', having),
                            ('ORDER BY', order_by)):
            if value:
                result.append(f'{name} {value}')
        # GenroPy _smartappend: a falsy limit or offset emits no clause.
        if limit:
            result.append(f'LIMIT {limit}')
        if offset:
            result.append(f'OFFSET {offset}')
        if for_update:
            result.append(f'FOR UPDATE OF {maintable_as}')
        return '\n'.join(result)

    # ------------------------------------------------------------------
    #  Statement preparation, after legacy execute and prepareSqlText
    # ------------------------------------------------------------------

    def prepare_sql(self, sql, sqlargs, snapshot) -> CompiledQuery:
        params, keys = prepare_arguments(sql, sqlargs, snapshot)
        # execute shields escaped colons before adapter.prepareSqlText, then restores.
        sql = sql.replace(r'\:', chr(1))
        used = {name for name, _ in SQL_PARAMS.findall(sql)}
        # GenroPy 5ddb6813dc defaults missing bindings to None. Materialize them
        # before CompiledQuery freezes the mapping and execution copies it to a dict.
        for name in sorted(used):
            params.setdefault(name, None)
        sql, params = self.prepareSqlText(sql, params)
        sql = sql.replace(chr(1), ':')
        binding = (EnvironmentBinding(tuple(sorted(keys)),
                                      {key: snapshot[key] for key in keys if key in snapshot})
                   if keys else None)
        return CompiledQuery(sql, params, dialect=self.dialect, binding=self.binding,
                             environment=binding, input_parameters=tuple(sorted(used)))

    def prepareSqlText(self, sql, kwargs):
        """Legacy prepareSqlText: backend syntax and parameters; returns (sql, kwargs)."""
        return self.adaptTupleListSet(sql, kwargs), kwargs

    def adaptTupleListSet(self, sql, sqlargs):
        """Legacy adaptTupleListSet, including its generated names."""
        for key, values in [(k, v) for k, v in list(sqlargs.items())
                            if isinstance(v, (list, tuple, set))]:
            placeholders = '(%s) ' % ','.join(':%s%i' % (key, i) for i, _ in enumerate(values))
            sqlargs.pop(key)
            sqlargs.update(('%s%i' % (key, i), value) for i, value in enumerate(values))
            sql = re.sub(r':%s(\W|$)' % key, placeholders + r'\1', sql)
        return sql

    # ------------------------------------------------------------------
    #  Connection and cursor
    # ------------------------------------------------------------------

    def validate(self, query: CompiledQuery) -> None:
        if not isinstance(query, CompiledQuery):
            raise TypeError('execute requires a CompiledQuery')
        if (query.dialect, query.binding) != (self.dialect, self.binding):
            raise ValueError(
                f'Query profile {query.dialect}/{query.binding} does not match '
                f'adapter profile {self.dialect}/{self.binding}')

    def cursor(self, connection):
        """A cursor that closes as a context manager, as DB-API 2 psycopg cursors do."""
        return connection.cursor()

    def _params(self, params):
        return dict(params)

    def execute(self, connection, query: CompiledQuery) -> QueryResult:
        self.validate(query)
        with self.cursor(connection) as cursor:
            cursor.execute(query.sql, self._params(query.params))
            names = [column[0] for column in cursor.description] if cursor.description is not None else None
            return query_result(query.columns, names, cursor)

    def executemany(self, connection, query: CompiledQuery, params_seq) -> QueryResult:
        """One statement, one parameter mapping per execution; no result rows."""
        self.validate(query)
        with self.cursor(connection) as cursor:
            cursor.executemany(query.sql, [self._params(params) for params in params_seq])
            return QueryResult([], cursor.rowcount, ())

    def commit(self, connection) -> None:
        connection.commit()

    def rollback(self, connection) -> None:
        connection.rollback()

    def close(self, connection) -> None:
        connection.close()

    # ------------------------------------------------------------------
    #  SQL functions for table formulas, as legacy
    # ------------------------------------------------------------------

    def string_agg(self, fieldpath, separator):
        """Legacy string_agg: a string_agg() SQL expression."""
        return f"string_agg({fieldpath},{sql_literal(separator)})"

    def unaccentFormula(self, field):
        """Legacy unaccentFormula: the field unchanged where the backend has no unaccent."""
        return field

    def ageAtDate(self, dateColumn, dateArg=None, timeUnit='day'):
        """Legacy ageAtDate: age of dateColumn at :dateArg (default the workdate) in timeUnit."""
        if timeUnit not in _TIME_UNITS:
            raise ValueError(f'ageAtDate: unknown timeUnit {timeUnit!r}; use one of {sorted(_TIME_UNITS)}')
        dateArg = dateArg or 'env_workdate'
        return ('CAST((EXTRACT (EPOCH FROM(cast(:%s as date))) -  \n'
                '                        EXTRACT (EPOCH FROM(%s)))/%i as bigint)'
                % (dateArg, dateColumn, _TIME_UNITS[timeUnit]))

    def mask_field_sql(self, field, mode='2-4', placeholder='*'):
        """Legacy mask_field_sql: modes 'email', 'creditcard', 'phone' or 'N-M'."""
        raise UnsupportedFeatureError(f'{self.dialect}: mask_field_sql is not available in this release')
