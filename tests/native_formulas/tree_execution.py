"""Test-only terminals: compile on the hierarchy, execute on a separate fixture.

count executes the hierarchical count compiler and interprets rows as legacy does.
DDL/metadata helpers delegate to the fixture; SELECT never uses its compiler.
"""


class ExecutedQuery:
    def __init__(self, query, executor):
        self.query, self.executor = query, executor

    @property
    def compiled(self):
        return self.query.compiled

    def fetch(self):
        return self.executor.execute(self.compiled).fetchall()

    def count(self):
        compiled = self.query._compile(self.query.db.compiler.count)
        cursor = self.executor.execute(compiled)
        rows = cursor.fetchall()
        if len(rows) == 1 and cursor.description[0][0] == 'gnr_row_count':
            return int(rows[0][0])
        return len(rows)


class ExecutionTable:
    def __init__(self, table, executor):
        self.table, self.executor = table, executor

    def query(self, columns='*', **kwargs):
        return ExecutedQuery(self.table.query(columns, **kwargs), self.executor)


class TreeExecution:
    def __init__(self, tree, executor, package=None):
        self.tree, self.executor, self.package = tree, executor, package

    def __getattr__(self, name):
        return getattr(self.executor, name)

    def table(self, name):
        if '.' not in name and self.package:
            name = self.package + '.' + name
        return ExecutionTable(self.tree.table(name), self.executor)
