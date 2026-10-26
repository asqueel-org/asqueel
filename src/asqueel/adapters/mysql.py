"""MySQL adapter on PyMySQL, for MySQL 8.0.19 or later.

Every connection adds ANSI_QUOTES, PIPES_AS_CONCAT and NO_BACKSLASH_ESCAPES
to the session sql_mode: identifiers are double-quoted, ``||`` concatenates
and string literals follow the standard rule, as in the SQL the compilers
write and as in the asqueel-migration MySQL DDL.

MySQL has no RETURNING, no deferred constraints and no transactional DDL.
SQL schemas are MySQL databases on the same server.
"""
from __future__ import annotations

from contextlib import closing
from datetime import time, timedelta
import re
from typing import Any

from ..contracts import UnsupportedFeatureError
from .._sql_parameters import substitute_parameters
from .base import SqlDbAdapter as SqlDbBaseAdapter, mask_bounds, sql_literal
from .postgres import SqlDbAdapter as PostgresAdapter


#: Session sql_mode flags added to the server's own mode.
SQL_MODE_FLAGS = ('ANSI_QUOTES', 'PIPES_AS_CONCAT', 'NO_BACKSLASH_ESCAPES')

#: The tokens the adapter rewrites or refuses, outside literals, identifiers and comments.
_TOKENS = re.compile(
    r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`"
    r"|--[^\r\n]*|\#[^\r\n]*|/\*[\s\S]*?\*/"
    r"|(?<![\w:$@])(?P<ilike>ILIKE)(?![\w$])"
    r"|(?P<regexp>~\*)"
    r"|(?<![\w:$@])(?P<default_values>DEFAULT\s+VALUES)(?![\w$])"
    r"|(?<![\w:$@])(?P<returning>RETURNING)(?![\w$])"
    r"|^\s*(?P<lock>LOCK)(?![\w$])",
    re.I,
)

#: MySQL limit of an unbounded OFFSET: the largest unsigned BIGINT.
_NO_LIMIT = 18446744073709551615


def _time(value):
    """PyMySQL reads TIME as timedelta; a time of day is a datetime.time."""
    if isinstance(value, timedelta):
        seconds = int(value.total_seconds())
        if not 0 <= seconds < 24 * 60 * 60:
            raise ValueError(f'MySQL TIME {value} is not a time of day')
        return time(seconds // 3600, seconds // 60 % 60, seconds % 60, value.microseconds)
    return value


class SqlDbAdapter(SqlDbBaseAdapter):
    """MySQL SQL and PyMySQL named parameter bindings."""

    dialect = 'mysql'
    binding = 'pymysql_named'
    capabilities = frozenset({
        'select', 'insert', 'update', 'delete', 'left_join', 'limit', 'offset',
        'default_values', 'for_update',
    })

    def connect(self, conninfo: str = '', *, dbname=None, host=None, port=None, user=None,
                password=None, connect_timeout=None, **kwargs: Any) -> Any:
        if conninfo:
            raise ValueError('MySQL takes connection fields (name, host, port, user, password), '
                             'not a conninfo string')
        if 'foreignKeys' in kwargs:
            raise ValueError('foreignKeys is a SQLite connection option, not available on MySQL')
        if kwargs.get('autocommit'):
            raise ValueError('autocommit is incompatible with explicit transactions')
        if kwargs:
            raise ValueError(f'Unsupported MySQL options: {sorted(kwargs)}')
        if not dbname:
            raise ValueError('MySQL requires a database name')
        # PyMySQL is the MySQL extra: imported only when connecting.
        import pymysql
        from pymysql.constants import FIELD_TYPE
        from pymysql.converters import conversions

        converters = dict(conversions)
        converters[FIELD_TYPE.TIME] = lambda value: _time(conversions[FIELD_TYPE.TIME](value))
        options = dict(host=host, port=int(port) if port is not None else None, user=user,
                       password=password, connect_timeout=connect_timeout)
        connection = pymysql.connect(database=dbname, charset='utf8mb4', autocommit=False, conv=converters,
                                     cursorclass=_cursor_class(),
                                     **{key: value for key, value in options.items() if value is not None})
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION sql_mode = CONCAT_WS(',', NULLIF(@@sql_mode, ''), %s)",
                               (','.join(SQL_MODE_FLAGS),))
        except BaseException:
            connection.close()
            raise
        return connection

    def cursor(self, connection, cursorname=None):
        """The connection's buffered cursor; tinyint(1) columns read as bool.

        ``cursorname`` is ignored: a PyMySQL unbuffered cursor blocks the
        connection until it is consumed.
        """
        return connection.cursor()

    def vacuum(self, table='', full=False):
        """``OPTIMIZE TABLE`` on ``table`` or on every model table, on a separate connection.

        OPTIMIZE TABLE commits implicitly, so it never runs on the application
        connection. InnoDB always rebuilds the table, so ``full`` adds nothing.
        """
        if table:
            names = [table]
        else:
            fullname = self.dbroot.write_compiler.sql_fullname
            names = [fullname(model) for model in self.dbroot.model.tables.values()]
        conninfo, connect_kwargs = self.dbroot._connection_settings()
        with closing(self.connect(conninfo, **connect_kwargs)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f'OPTIMIZE TABLE {", ".join(names)}')
                cursor.fetchall()

    def analyze(self):
        """ANALYZE TABLE commits implicitly: it cannot run in the current transaction."""
        raise UnsupportedFeatureError('mysql: analyze is not available; ANALYZE TABLE commits implicitly')

    def setConstraintsDeferred(self):
        raise UnsupportedFeatureError('mysql: deferred constraints are not available')

    # ------------------------------------------------------------------
    #  Statement preparation
    # ------------------------------------------------------------------

    #: IN lists unrolled as for psycopg 3; an empty list gives TRUE/FALSE.
    adaptTupleListSet = PostgresAdapter.adaptTupleListSet

    def prepareSqlText(self, sql, kwargs):
        """ILIKE as LIKE, ``~*`` as REGEXP, DEFAULT VALUES as ``() VALUES ()``; ``%(name)s`` bindings.

        RETURNING and LOCK raise: MySQL has neither. PyMySQL formats every
        statement with ``%``, so a literal ``%`` is doubled.
        """
        sql = self.adaptTupleListSet(sql, kwargs)
        sql = _TOKENS.sub(self._token, sql)
        sql = sql.replace('%', '%%')
        return substitute_parameters(sql, lambda m: '%(' + m['parameter'] + ')s', self.dialect), kwargs

    @staticmethod
    def _token(match):
        if match['returning']:
            raise UnsupportedFeatureError('mysql: RETURNING is not available')
        if match['lock']:
            raise UnsupportedFeatureError('mysql: table locks are not available; LOCK TABLES commits implicitly')
        if match['ilike']:
            return 'LIKE'
        if match['regexp']:
            return ' REGEXP '
        if match['default_values']:
            return '() VALUES ()'
        return match[0]

    def adaptSqlName(self, name: str) -> str:
        quoted = super().adaptSqlName(name)
        if len(name) > 64:
            raise ValueError('MySQL identifiers must not exceed 64 characters')
        return quoted

    def compileSql(self, maintable, columns, distinct='', joins=None, where=None,
                   group_by=None, having=None, order_by=None, limit=None, offset=None,
                   for_update=False, maintable_as='t0'):
        if offset and not limit:
            limit = _NO_LIMIT
        return super().compileSql(maintable, columns, distinct, joins, where, group_by,
                                  having, order_by, limit, offset, for_update, maintable_as)

    # ------------------------------------------------------------------
    #  SQL functions
    # ------------------------------------------------------------------

    def string_join(self, expressions, separator):
        """CONCAT_WS skips NULL terms and keeps empty strings, as legacy string_join."""
        if not expressions:
            return "''"
        return f"CONCAT_WS({sql_literal(separator)}, {', '.join(expressions)})"

    def concat_template(self, parts):
        # MySQL CONCAT gives NULL when a term is NULL; COALESCE keeps the '' rule.
        terms = [sql_literal(text) if literal else f"COALESCE(CAST(({text}) AS CHAR), '')"
                 for text, literal in parts]
        return f"CONCAT({', '.join(terms)})" if terms else "''"

    def string_agg(self, fieldpath, separator):
        return f'GROUP_CONCAT({fieldpath} SEPARATOR {sql_literal(separator)})'

    def join_sql_subquery(self, sql, alias):
        raise UnsupportedFeatureError('mysql: a join aggregate needs a per-row separator; '
                                      'GROUP_CONCAT takes only a literal separator')

    def json_sql_subquery(self, sql, alias, columns):
        raise UnsupportedFeatureError('mysql: JSON_ARRAYAGG does not keep the row order of the subquery')

    def xml_sql_subquery(self, sql, alias, columns):
        raise UnsupportedFeatureError('mysql: to_xml (Bag XML) is not available')

    def aggregate_sql_subquery(self, sql, mode, alias, columns):
        raise UnsupportedFeatureError(f'mysql: subQueryColumn mode={mode!r} is not available')

    def bag_item_formula(self, bagcolumn, dtype):
        raise UnsupportedFeatureError('mysql: bagItemColumn XPath extraction is not available')

    def ageAtDate(self, dateColumn, dateArg=None, timeUnit='day'):
        raise UnsupportedFeatureError('mysql: ageAtDate is not available; the legacy SQL needs EXTRACT(EPOCH ...)')

    def mask_field_sql(self, field, mode='2-4', placeholder='*'):
        """The PostgreSQL masking expression in MySQL functions; lengths in characters."""
        placeholder = placeholder.replace("'", "''")
        if mode == 'email':
            return f"""
                CASE
                    WHEN position('@' in {field}) > 0 THEN
                        substring({field} from 1 for 2) ||
                        repeat('{placeholder}', greatest(char_length(SUBSTRING_INDEX({field}, '@', 1)) - 2, 0)) ||
                        '@' ||
                        SUBSTRING_INDEX({field}, '@', -1)
                    ELSE
                        {field}
                END
            """.strip()
        if mode == 'creditcard':
            visible_start, visible_end = 0, 4
        elif mode == 'phone':
            visible_start, visible_end = 3, 3
        else:
            visible_start, visible_end = mask_bounds(mode)
        return f"""
                CASE
                    WHEN char_length({field}) > {visible_start + visible_end} THEN
                        substring({field} from 1 for {visible_start}) ||
                        repeat('{placeholder}', char_length({field}) - {visible_start} - {visible_end}) ||
                        right({field}, {visible_end})
                    ELSE
                        {field}
                END
            """.strip()


def _cursor_class():
    """A buffered PyMySQL cursor that reads tinyint(1), the boolean type of the migration DDL, as bool."""
    from pymysql.constants import FIELD_TYPE
    from pymysql.cursors import Cursor

    class MysqlCursor(Cursor):
        def _do_get_result(self):
            super()._do_get_result()
            fields = self._result.fields if self.description else ()
            flags = [field.type_code == FIELD_TYPE.TINY and field.length == 1 for field in fields]
            if any(flags) and self._rows:
                self._rows = tuple(
                    tuple(bool(value) if flag and value is not None else value
                          for value, flag in zip(row, flags))
                    for row in self._rows)

    return MysqlCursor
