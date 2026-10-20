"""SQLite generated-column introspection missing from asqueel-migration 0.3.x.

Keep normalization and migration planning in the dependency. Only enrich its
catalog rows: table_info omits generated columns, whereas table_xinfo includes
them. Read expressions from the actual schema, never from the desired model.
"""
import re

from asqueel_migration import SqliteDatabase
from asqueel_migration.adapters.sqlite_adapter import SqliteAdapter
from asqueel_migration.readers import SqliteReader

from .errors import MigrationError


# Tokenize only SQLite quotes and comments; preserve every source offset.
_SQLITE_QUOTED = re.compile(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^\]]*\]|--[^\r\n]*|/\*[\s\S]*?\*/")


def sqlite_tokens(sql):
    start = 0
    for match in _SQLITE_QUOTED.finditer(sql):
        yield 'code', sql[start:match.start()]
        text = match.group()
        yield ('comment' if text.startswith(('--', '/*')) else 'quoted'), text
        start = match.end()
    yield 'code', sql[start:]


def generated_expressions(sql):
    # Preserve offsets while masking literals, quoted identifiers and comments.
    tokens = list(sqlite_tokens(sql))
    masked = ''.join(value if kind == 'code' else ' ' * len(value) for kind, value in tokens)
    uncommented = ''.join(' ' * len(value) if kind in ('comment', 'line_comment') else value
                          for kind, value in tokens)
    start = masked.index('(') + 1
    depth, result = 0, {}
    identifier = re.compile(r'\s*("(?:[^"]|"")*"|`(?:[^`]|``)*`|\[[^\]]*\]|[^\s(]+)')
    for index in range(start, len(masked)):
        char = masked[index]
        if char == '(':
            depth += 1
        elif char == ')' and depth:
            depth -= 1
        elif char in ',)' and not depth:
            fragment = masked[start:index]
            clause = re.search(r'\bAS\s*\(', fragment, re.IGNORECASE)
            if clause:
                name = identifier.match(uncommented[start:index])
                expression_start = start + clause.end()
                expression_end, balance = expression_start, 1
                while expression_end < index and balance:
                    if masked[expression_end] == '(':
                        balance += 1
                    elif masked[expression_end] == ')':
                        balance -= 1
                    expression_end += 1
                if name is None or balance:
                    raise MigrationError('Cannot introspect SQLite generated expression')
                result[SqliteReader._unquote(name.group(1))] = sql[expression_start:expression_end - 1].strip()
            start = index + 1
            if char == ')':
                break
    return result


class GeneratedColumnReader(SqliteReader):
    def fetch_base_structure(self, schemas):
        columns = super().fetch_base_structure(schemas)
        existing = {(col['_pg_schema_name'], col['_pg_table_name'], col['name']) for col in columns}
        for schema in schemas:
            tables = self._fetch(f'SELECT name, sql FROM {self.quote_identifier(schema)}.sqlite_master '
                                 "WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            for table, sql in tables:
                expressions = None
                for _, name, declared, notnull, default, _, hidden in self._fetch(
                        f'PRAGMA {self.quote_identifier(schema)}.table_xinfo({self.quote_identifier(table)})'):
                    if hidden not in (2, 3) or (schema, table, name) in existing:
                        continue
                    if expressions is None:
                        expressions = generated_expressions(sql)
                    if name not in expressions:
                        raise MigrationError(f'Cannot introspect generated column {schema}.{table}.{name}')
                    dtype, size = self._reverse_type(declared)
                    column = dict(_pg_schema_name=schema, _pg_table_name=table, name=name, dtype=dtype,
                                  _pg_is_nullable='NO' if notnull else 'YES', sqldefault=default,
                                  generated_expression=expressions[name])
                    if size is not None:
                        column['size'] = size
                    columns.append(column)
        return columns


class GeneratedColumnAdapter(SqliteAdapter):
    @property
    def reader(self):
        if self._reader is None:
            self._reader = GeneratedColumnReader(self.database.connection_params(),
                                                  schemas=self.database.schema_files())
        return self._reader


class SqliteMigrationDatabase(SqliteDatabase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._adapter = GeneratedColumnAdapter(self)
