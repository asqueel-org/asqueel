"""SQLite rendering with attached schemas and connection-level write locking."""

from .postgres import PostgresDialect
from ..contracts import UnsupportedFeatureError
from .._legacy_sql import split_sql


class SqliteDialect(PostgresDialect):
    """Common SELECT/DML syntax; SQLite-specific RETURNING and pagination."""

    name = 'sqlite'

    def bag_item_formula(self, bagcolumn, dtype):
        raise UnsupportedFeatureError('SQLite does not support legacy bagItemColumn XPath extraction')


    def join_sql_subquery(self, sql, alias):
        """Concatenate an ordered row source, preserving empty-value positions."""
        row = self.quote_identifier(alias)
        return (f"(SELECT COALESCE(group_concat({row}.value, {row}.separator), '') "
                f'FROM ({sql}) AS {row})')

    def json_sql_subquery(self, sql, alias, columns):
        """Build JSON objects from the query's selected names and native values."""
        row = self.quote_identifier(alias)
        fields = []
        for column in split_sql(columns):
            # The legacy may omit result metadata for authored aliases. Read
            # the actual projection instead: SQLite keeps an unquoted alias's
            # case and names an unaliased expression after its SQL text.
            parts = split_sql(column, ' AS ')
            name = parts[-1].strip()
            if len(parts) == 2 and name.startswith('"') and name.endswith('"'):
                name = name[1:-1].replace('""', '"')
            fields.extend(["'" + name.replace("'", "''") + "'", row + '.' + self.quote_identifier(name)])
        return f'(SELECT json_group_array(json_object({", ".join(fields)})) FROM ({sql}) AS {row})'

    def xml_sql_subquery(self, sql, alias, columns):
        raise UnsupportedFeatureError('SQLite does not support to_xml (Bag XML)')

    def aggregate_sql_subquery(self, sql, mode, alias, columns):
        raise UnsupportedFeatureError(f'SQLite does not support legacy subQueryColumn mode={mode!r}')


    def quote_identifier(self, name):
        if not isinstance(name, str) or not name or '\x00' in name:
            raise ValueError('SQL identifiers must be nonempty strings without NUL')
        return '"' + name.replace('"', '""') + '"'

    def empty_collection(self, negated):
        # SQLite has no array literal; an empty row source is the portable form.
        return 'NOT IN (SELECT 1 WHERE 0)' if negated else 'IN (SELECT 1 WHERE 0)'

    def concat_non_null(self, expressions, separator):
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


    def compile_sql(self, maintable, columns, distinct='', joins=None, where=None,
                    group_by=None, having=None, order_by=None, limit=None, offset=None,
                    for_update=False, maintable_as='t0'):
        if for_update:
            self._require('for_update')
        if offset is not None and limit is None:
            limit = 9223372036854775807
        return super().compile_sql(maintable, columns, distinct, joins, where, group_by,
                                   having, order_by, limit, offset, False, maintable_as)
