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
from .base import SqlDbAdapter as SqlDbBaseAdapter, mask_bounds, sql_literal


_ILIKE = re.compile(
    r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^\]]*\]"
    r"|--[^\r\n]*|/\*[\s\S]*?\*/|(?<![\w:$@])(?P<operator>ILIKE)(?![\w$])",
    re.I,
)


class SqlDbAdapter(SqlDbBaseAdapter):
    """Common SELECT/DML syntax; SQLite-specific RETURNING and pagination."""

    dialect = 'sqlite'
    binding = 'sqlite_named'
    capabilities = frozenset({
        'select', 'insert', 'update', 'delete', 'returning_insert',
        'returning_update', 'returning_delete', 'left_join', 'limit', 'offset',
        'default_values', 'for_update',
    })

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

    def cursor(self, connection):
        # sqlite3 cursors are not context managers.
        return closing(connection.cursor())

    def _begin(self, connection, query):
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
        self._begin(connection, query)
        return super().executemany(connection, query, params_seq)

    def _params(self, params):
        return {name: self._value(value) for name, value in params.items()}

    @staticmethod
    def _value(value):
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        return value

    def prepareSqlText(self, sql, kwargs):
        """Legacy gnrsqlite: ILIKE as LIKE, ``~*`` as REGEXP, IS TRUE/FALSE on 0/1."""
        sql = self.adaptTupleListSet(sql, kwargs)
        # Adapt only the ILIKE token, keeping quoted SQL and bindings intact.
        sql = _ILIKE.sub(lambda match: match['operator'][1:] if match['operator'] else match[0], sql)
        sql = sql.replace('~*', ' REGEXP ')
        sql = re.sub(r'(\(*)(["\w]["\w.]*) +IS +(NOT +)?(TRUE|FALSE)',
                     self._booleanSubCb, sql, flags=re.I)
        return sql, kwargs

    def _booleanSubCb(self, match):
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

    def string_join(self, expressions, separator):
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

    def compileSql(self, maintable, columns, distinct='', joins=None, where=None,
                   group_by=None, having=None, order_by=None, limit=None, offset=None,
                   for_update=False, maintable_as='t0'):
        if for_update:
            self._require('for_update')
        if offset and not limit:
            limit = 9223372036854775807
        return super().compileSql(maintable, columns, distinct, joins, where, group_by,
                                  having, order_by, limit, offset, False, maintable_as)

    def string_agg(self, fieldpath, separator):
        return f"group_concat({fieldpath},{sql_literal(separator)})"

    def ageAtDate(self, dateColumn, dateArg=None, timeUnit='day'):
        raise UnsupportedFeatureError('SQLite does not support ageAtDate: the legacy SQL needs EXTRACT(EPOCH ...)')

    def mask_field_sql(self, field, mode='2-4', placeholder='*'):
        """Legacy SQLite masking expression; SQLite has no repeat(), so a mask string is cut."""
        placeholder = placeholder.replace("'", "''")
        max_mask_chars = 100  # Maximum mask length supported
        mask_base = '*' * max_mask_chars

        if mode == 'email':
            # Mask local part of email, keep domain visible (default 2 chars visible at start)
            sql_formula = f"""
                CASE
                    WHEN instr({field}, '@') > 0 THEN
                        substr({field}, 1, 2) ||
                        replace(substr('{mask_base}', 1, max(instr({field}, '@') - 1 - 2, 0)), '*', '{placeholder}') ||
                        substr({field}, instr({field}, '@'))
                    ELSE
                        {field}
                END
            """.strip()

        elif mode == 'creditcard':
            # Show only last 4 digits
            sql_formula = f"""
                CASE
                    WHEN length({field}) > 4 THEN
                        replace(substr('{mask_base}', 1, length({field}) - 4), '*', '{placeholder}') ||
                        substr({field}, -4)
                    ELSE
                        {field}
                END
            """.strip()

        elif mode == 'phone':
            # Keep country code (3 chars) and last 3 digits visible
            sql_formula = f"""
                CASE
                    WHEN length({field}) > 6 THEN
                        substr({field}, 1, 3) ||
                        replace(substr('{mask_base}', 1, length({field}) - 6), '*', '{placeholder}') ||
                        substr({field}, -3)
                    ELSE
                        {field}
                END
            """.strip()

        else:
            visible_start, visible_end = mask_bounds(mode)
            sql_formula = f"""
                CASE
                    WHEN length({field}) > {visible_start + visible_end} THEN
                        substr({field}, 1, {visible_start}) ||
                        replace(substr('{mask_base}', 1, length({field}) - {visible_start} - {visible_end}), '*', '{placeholder}') ||
                        substr({field}, -{visible_end})
                    ELSE
                        {field}
                END
            """.strip()

        return sql_formula
