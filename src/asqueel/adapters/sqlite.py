"""SQLite adapter on the stdlib driver, after legacy ``gnrsqlite``.

Attached schemas and connection-level write locking.
"""
from __future__ import annotations

from contextlib import closing
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import re
import sqlite3

from .._legacy_sql import split_sql
from ..contracts import UnsupportedFeatureError
from .postgres import SqlDbAdapter as PostgresAdapter
from .base import SqlDbAdapter as SqlDbBaseAdapter


_ILIKE = re.compile(
    r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^\]]*\]"
    r"|--[^\r\n]*|/\*[\s\S]*?\*/|(?<![\w:$@])(?P<operator>ILIKE)(?![\w$])",
    re.I,
)


class SqlDbAdapter(SqlDbBaseAdapter):
    """Common SELECT/DML syntax; SQLite-specific RETURNING and pagination."""

    dialect = 'sqlite'
    binding = 'sqlite_named'
    capabilities = PostgresAdapter.capabilities

    def connect(self, conninfo='', *, dbname=None, schemas=(), **kwargs):
        if sqlite3.sqlite_version_info < (3, 35, 0):
            raise RuntimeError('SQLite 3.35 or later is required for RETURNING')
        if conninfo and dbname:
            raise ValueError('Supply a SQLite filename once')
        name = dbname or conninfo
        if not name:
            raise ValueError('SQLite requires a database filename or :memory:')
        allowed = {'timeout', 'cached_statements'}
        if set(kwargs) - allowed:
            raise ValueError(f'Unsupported SQLite options: {sorted(set(kwargs) - allowed)}')
        connection = sqlite3.connect(name, isolation_level=None, **kwargs)
        try:
            # gnrsqlite registers this function for its ~* -> REGEXP translation.
            connection.create_function('regexp', 2, self._regexp)
            connection.execute('PRAGMA foreign_keys = ON')
            for schema in schemas:
                if schema == 'main':
                    continue
                if not isinstance(schema, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', schema) or schema == 'temp':
                    raise ValueError('SQLite attached schema names must be simple identifiers other than temp')
                # Same file layout as asqueel_migration.SqliteDatabase.schema_files().
                path = ':memory:' if name == ':memory:' else str(Path(name).with_name(f'{Path(name).stem}_{schema}.db'))
                connection.execute(f'ATTACH DATABASE ? AS "{schema}"', (path,))
        except BaseException:
            connection.close()
            raise
        return connection

    @staticmethod
    def _regexp(expression, item):
        return re.compile(expression, re.U).match(item) is not None

    def cursor(self, connection):  # wf:phase-2:new
        # sqlite3 cursors are not context managers.
        return closing(connection.cursor())

    def _begin(self, connection, query):  # wf:phase-2:new
        """Explicit transaction boundary; a locked query takes the write reservation."""
        if not connection.in_transaction:
            connection.execute('BEGIN IMMEDIATE')
        elif query.for_update:
            if not query.lock_table or not query.lock_column:
                raise ValueError('A locked SQLite query requires a physical table and column')
            # Acquire the write reservation without changing rows or ending the transaction.
            connection.execute(f'UPDATE {query.lock_table} SET {query.lock_column}={query.lock_column} WHERE 0')

    def execute(self, connection, query):
        self.validate(query)
        self._begin(connection, query)
        return super().execute(connection, query)

    def executemany(self, connection, query, params_seq):
        """One statement, one parameter mapping per execution; no result rows."""
        self.validate(query)
        if not connection.in_transaction:
            connection.execute('BEGIN IMMEDIATE')
        return super().executemany(connection, query, params_seq)

    def _params(self, params):  # wf:phase-2:new
        return {name: self._value(value) for name, value in params.items()}

    @staticmethod
    def _value(value):
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        return value

    def prepareSqlText(self, sql, kwargs):  # wf:phase-2:new
        """Legacy gnrsqlite: ILIKE as LIKE, ``~*`` as REGEXP, IS TRUE/FALSE on 0/1."""
        sql = self.adaptTupleListSet(sql, kwargs)
        # Adapt only the ILIKE token, keeping quoted SQL and bindings intact.
        sql = _ILIKE.sub(lambda match: match['operator'][1:] if match['operator'] else match[0], sql)
        sql = sql.replace('~*', ' REGEXP ')
        sql = re.sub(r'(\(*)(["\w]["\w.]*) +IS +(NOT +)?(TRUE|FALSE)',
                     self._booleanSubCb, sql, flags=re.I)
        return sql, kwargs

    def _booleanSubCb(self, match):  # wf:phase-2:new
        """gnrsqlite._booleanSubCb."""
        prefix, expr, is_not, truth = match.groups()
        value = '1' if truth.upper() == 'TRUE' else '0'
        if is_not:
            return '%s(%s IS NULL OR %s !=%s)' % (prefix, expr, expr, value)
        return '%s(%s IS NOT NULL AND %s =%s)' % (prefix, expr, expr, value)

    def bag_item_formula(self, bagcolumn, dtype):
        raise UnsupportedFeatureError('SQLite does not support legacy bagItemColumn XPath extraction')

    def join_sql_subquery(self, sql, alias):
        """Concatenate an ordered row source, preserving empty-value positions."""
        row = self.adaptSqlName(alias)
        return (f"(SELECT COALESCE(group_concat({row}.value, {row}.separator), '') "
                f'FROM ({sql}) AS {row})')

    def json_sql_subquery(self, sql, alias, columns):
        """Build JSON objects from the query's selected names and native values."""
        row = self.adaptSqlName(alias)
        fields = []
        for column in split_sql(columns):
            # The legacy may omit result metadata for authored aliases. Read
            # the actual projection instead: SQLite keeps an unquoted alias's
            # case and names an unaliased expression after its SQL text.
            parts = split_sql(column, ' AS ')
            name = parts[-1].strip()
            if len(parts) == 2 and name.startswith('"') and name.endswith('"'):
                name = name[1:-1].replace('""', '"')
            fields.extend(["'" + name.replace("'", "''") + "'", row + '.' + self.adaptSqlName(name)])
        return f'(SELECT json_group_array(json_object({", ".join(fields)})) FROM ({sql}) AS {row})'

    def xml_sql_subquery(self, sql, alias, columns):
        raise UnsupportedFeatureError('SQLite does not support to_xml (Bag XML)')

    def aggregate_sql_subquery(self, sql, mode, alias, columns):
        raise UnsupportedFeatureError(f'SQLite does not support legacy subQueryColumn mode={mode!r}')

    def empty_collection(self, negated):
        # SQLite has no array literal; an empty row source is the portable form.
        return 'NOT IN (SELECT 1 WHERE 0)' if negated else 'IN (SELECT 1 WHERE 0)'

    def string_join(self, expressions, separator):  # wf:phase-2:new
        # Prefix each non-NULL term, then remove exactly the first separator.
        # Unlike trim(), this preserves separator characters in the values.
        literal = "'" + separator.replace("'", "''") + "'"
        terms = [f"COALESCE({literal} || ({expression}), '')" for expression in expressions]
        joined = ' || '.join(terms) or "''"
        return f'substr({joined}, {len(separator) + 1})'

    def concat_template(self, parts):
        # concat() needs SQLite 3.44; COALESCE keeps the same NULL rule on 3.35.
        terms = [f"'{text.replace(chr(39), chr(39) * 2)}'" if literal
                 else f"COALESCE(CAST(({text}) AS TEXT), '')" for text, literal in parts]
        return f"({' || '.join(terms) or chr(39) * 2})"

    def compileSql(self, maintable, columns, distinct='', joins=None, where=None,  # wf:phase-2:new
                   group_by=None, having=None, order_by=None, limit=None, offset=None,
                   for_update=False, maintable_as='t0'):
        if for_update:
            self._require('for_update')
        if offset is not None and limit is None:
            limit = 9223372036854775807
        return super().compileSql(maintable, columns, distinct, joins, where, group_by,
                                  having, order_by, limit, offset, False, maintable_as)
