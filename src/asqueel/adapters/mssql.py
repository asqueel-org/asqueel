"""Microsoft SQL Server adapter on pymssql.

pymssql is the driver asqueel-migration uses for SQL Server. Its ``pyformat``
paramstyle takes ``%(name)s`` bindings, as psycopg. Identifiers are ANSI
``"…"``: pymssql opens every connection with ``QUOTED_IDENTIFIER ON``.

SQL that the shared compilers write in a form T-SQL lacks raises
``UnsupportedFeatureError`` here: ``||``, ``~*``/``REGEXP``, ``LOCK``,
row-value ``IN`` and ordered row-source aggregates.
"""
from __future__ import annotations

import re

from ..contracts import UnsupportedFeatureError
from .._sql_parameters import parameter_matches, substitute_parameters
from .base import SqlDbAdapter as SqlDbBaseAdapter, _TIME_UNITS


#: T-SQL operators outside literals, identifiers and comments.
_OPERATOR = re.compile(
    r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|\[(?:\]\]|[^\]])*\]"
    r"|--[^\r\n]*|/\*[\s\S]*?\*/"
    r"|(?P<operator>\|\||~\*|(?<![\w:$@])(?:ILIKE|REGEXP)(?![\w$]))",
    re.I,
)
#: A row-value IN: ``("a","b") IN (``.
_ROW_IN = re.compile(r'\(\s*"(?:""|[^"])*"(?:\s*,\s*"(?:""|[^"])*")+\s*\)\s*IN\s*\(', re.I)
_LOCK = re.compile(r'\s*LOCK\s', re.I)
_CONNECT_OPTIONS = frozenset({
    'host', 'server', 'port', 'user', 'password', 'dbname', 'timeout',
    'login_timeout', 'charset', 'appname', 'tds_version',
})


class SqlDbAdapter(SqlDbBaseAdapter):
    """SQL Server SQL and pymssql named parameter bindings."""

    dialect = 'mssql'
    binding = 'pymssql_named'
    capabilities = frozenset({
        'select', 'insert', 'update', 'delete', 'left_join', 'limit', 'offset',
        'default_values', 'for_update',
    })

    def connect(self, conninfo='', **kwargs):
        if conninfo:
            raise ValueError('SQL Server takes connection fields (host, port, user, password, dbname), not a conninfo string')
        if 'foreignKeys' in kwargs:
            raise ValueError('foreignKeys is a SQLite connection option, not available on SQL Server')
        if kwargs.get('autocommit'):
            raise ValueError('autocommit is incompatible with explicit transactions')
        unknown = set(kwargs) - _CONNECT_OPTIONS
        if unknown:
            raise ValueError(f'Unsupported SQL Server options: {sorted(unknown)}')
        # pymssql is the SQL Server extra: imported only when connecting.
        import pymssql

        if 'dbname' in kwargs:
            kwargs['database'] = kwargs.pop('dbname')
        # TDS 7.3 or later returns date, time and datetime2 as Python values.
        kwargs.setdefault('tds_version', '7.4')
        return pymssql.connect(autocommit=False, **kwargs)

    def setConstraintsDeferred(self):
        raise UnsupportedFeatureError('SQL Server has no deferrable constraints')

    def analyze(self):
        """Legacy analyze: the statistics of the whole database, in the current transaction."""
        self.dbroot.execute('EXEC sp_updatestats').close()

    def vacuum(self, table='', full=False):
        raise UnsupportedFeatureError('SQL Server has no VACUUM')

    def adaptSqlName(self, name: str) -> str:
        quoted = super().adaptSqlName(name)
        if len(name) > 128:
            raise ValueError('SQL Server identifiers must not exceed 128 characters')
        return quoted

    # ------------------------------------------------------------------
    #  Statement preparation
    # ------------------------------------------------------------------

    def prepareSqlText(self, sql, kwargs):
        """Named arguments as pymssql ``%(name)s``; ILIKE as LIKE; IS TRUE/FALSE on bit."""
        if _LOCK.match(sql):
            raise UnsupportedFeatureError('SQL Server has no LOCK statement')
        if _ROW_IN.search(sql):
            raise UnsupportedFeatureError('SQL Server has no row-value IN')
        sql = self.adaptTupleListSet(sql, kwargs)
        sql = _OPERATOR.sub(self._operator, sql)
        sql = re.sub(r'(\(*)(["\w]["\w.]*) +IS +(NOT +)?(TRUE|FALSE)',
                     self._booleanSubCb, sql, flags=re.I)
        return substitute_parameters(sql, lambda m: '%(' + m['parameter'] + ')s', self.dialect), kwargs

    @staticmethod
    def _operator(match):
        operator = match['operator']
        if not operator:
            return match[0]
        if operator.upper() == 'ILIKE':
            # LIKE follows the column collation, case-insensitive by default.
            return 'LIKE'
        if operator == '||':
            raise UnsupportedFeatureError('SQL Server has no || concatenation operator')
        raise UnsupportedFeatureError(f'SQL Server has no {operator} regular expression operator')

    def _booleanSubCb(self, match):
        """gnrsqlite._booleanSubCb, as the SQLite adapter: bit columns hold 1 or 0."""
        prefix, expr, is_not, truth = match.groups()
        value = '1' if truth.upper() == 'TRUE' else '0'
        if is_not:
            return '%s(%s IS NULL OR %s !=%s)' % (prefix, expr, expr, value)
        return '%s(%s IS NOT NULL AND %s =%s)' % (prefix, expr, expr, value)

    def adaptTupleListSet(self, sql, sqlargs):
        """An empty list makes ``IN`` false and ``NOT IN`` true, as gnrpostgres3; T-SQL has no TRUE."""
        for key, values in list(sqlargs.items()):
            if not isinstance(values, (list, set, tuple)) or values:
                continue
            pattern = r'''((\"?t\d+)(_t\d+)*\"?.\"?\w+\"?" +)(NOT +)*(IN) *:%s''' % key
            positions = {m.start() for m in parameter_matches(sql, self.dialect)}
            sql = re.sub(pattern, lambda m: ('(1=1)' if m.group(4) else '(1=0)')
                         if m.end() - len(key) - 1 in positions else m[0], sql, flags=re.I)
            sqlargs.pop(key)
        return super().adaptTupleListSet(sql, sqlargs)

    def compileSql(self, maintable, columns, distinct='', joins=None, where=None,
                   group_by=None, having=None, order_by=None, limit=None, offset=None,
                   for_update=False, maintable_as='t0'):
        """``TOP``, or ``OFFSET … FETCH`` after ORDER BY; FOR UPDATE as table hints."""
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
        if isinstance(for_update, str):
            raise UnsupportedFeatureError(f'for_update={for_update} is not available on SQL Server')
        top = f'TOP ({limit}) ' if limit and not offset else ''
        hints = ' WITH (UPDLOCK, ROWLOCK)' if for_update else ''
        result = [f'SELECT {distinct}{top}{columns}',
                  f' FROM {maintable} AS {self.adaptSqlName(maintable_as)}{hints}']
        for join in joins or ():
            self._require('left_join')
            result.append(f'       {join}')
        if offset and not order_by:
            # OFFSET needs an ORDER BY; this one keeps the server's row order.
            order_by = '(SELECT NULL)'
        for name, value in (('WHERE', where), ('GROUP BY', group_by), ('HAVING', having),
                            ('ORDER BY', order_by)):
            if value:
                result.append(f'{name} {value}')
        if offset:
            result.append(f'OFFSET {offset} ROWS')
            if limit:
                result.append(f'FETCH NEXT {limit} ROWS ONLY')
        return '\n'.join(result)

    # ------------------------------------------------------------------
    #  SQL functions for table formulas
    # ------------------------------------------------------------------

    def string_join(self, expressions, separator):
        """CONCAT_WS skips NULL terms and keeps empty strings, as legacy string_join."""
        if not expressions:
            return "''"
        literal = "'" + separator.replace("'", "''") + "'"
        # CONCAT_WS takes at least two terms; NULL adds nothing.
        terms = expressions if len(expressions) > 1 else [*expressions, 'NULL']
        return f"CONCAT_WS({literal}, {', '.join(terms)})"

    def ageAtDate(self, dateColumn, dateArg=None, timeUnit='day'):
        """Legacy ageAtDate: seconds from dateColumn to :dateArg, rounded in timeUnit."""
        if timeUnit not in _TIME_UNITS:
            raise ValueError(f'ageAtDate: unknown timeUnit {timeUnit!r}; use one of {sorted(_TIME_UNITS)}')
        dateArg = dateArg or 'env_workdate'
        # PostgreSQL rounds the numeric quotient when it casts it to bigint.
        return ('CAST(ROUND(DATEDIFF_BIG(second, %s, CAST(:%s AS date)) / CAST(%i AS numeric(38, 10)), 0) AS bigint)'
                % (dateColumn, dateArg, _TIME_UNITS[timeUnit]))

    def bag_item_formula(self, bagcolumn, dtype):
        raise UnsupportedFeatureError('SQL Server does not support legacy bagItemColumn XPath extraction')

    def join_sql_subquery(self, sql, alias):
        raise UnsupportedFeatureError('SQL Server does not support ordered join aggregates')

    def json_sql_subquery(self, sql, alias, columns):
        raise UnsupportedFeatureError('SQL Server does not support to_json subqueries')

    def xml_sql_subquery(self, sql, alias, columns):
        raise UnsupportedFeatureError('SQL Server does not support to_xml (Bag XML)')

    def aggregate_sql_subquery(self, sql, mode, alias, columns):
        raise UnsupportedFeatureError(f'SQL Server does not support legacy subQueryColumn mode={mode!r}')
