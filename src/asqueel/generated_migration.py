"""Detect generated-expression changes ignored by migration 0.3.x."""
from .sqlite_migration import sqlite_tokens


def check_generated_changes(migrator, implementation):
    desired_schemas = migrator.ormStructure.get('root', {}).get('schemas', {})
    actual_schemas = migrator.sqlStructure.get('root', {}).get('schemas', {})
    actual = {}
    for schema, data in actual_schemas.items():
        for table, definition in data.get('tables', {}).items():
            for name, column in definition.get('columns', {}).items():
                expression = column['attributes'].get('generated_expression')
                if expression:
                    actual[schema, table, name] = expression
    reader = migrator.db.adapter.reader
    connected = False
    try:
        # The PostgreSQL reader in 0.3.x omits generation_expression altogether.
        if implementation in ('postgres', 'postgres3') and actual_schemas:
            reader.connect()
            connected = True
            actual.update({(schema, table, name): expression for schema, table, name, expression
                           in reader._fetch('SELECT table_schema, table_name, column_name, generation_expression '
                                            'FROM information_schema.columns WHERE table_schema = ANY(%s) '
                                            "AND is_generated = 'ALWAYS'", (list(desired_schemas),))})
        for schema, data in desired_schemas.items():
            for table, definition in data.get('tables', {}).items():
                existing = actual_schemas.get(schema, {}).get('tables', {}).get(table, {}).get('columns', {})
                for name, column in definition.get('columns', {}).items():
                    if name not in existing:
                        continue
                    wanted = column['attributes'].get('generated_expression')
                    stored = actual.get((schema, table, name))
                    if wanted == stored:
                        continue
                    equal = False
                    if wanted and stored:
                        if implementation == 'sqlite':
                            tokens = sqlite_tokens
                            def normalize(sql):
                                return [(kind, value.strip() if kind == 'code' else value) for kind, value in tokens(sql)
                                        if kind not in ('comment', 'line_comment') and value.strip()]
                            equal = normalize(wanted) == normalize(stored)
                        else:
                            quote = migrator.db.adapter.writer.quote_identifier
                            target = quote(schema) + '.' + quote(table)
                            # PostgreSQL deparses with casts and parentheses. Let
                            # its planner normalize both expressions without
                            # executing the SELECT or changing the schema.
                            try:
                                plan = reader._fetch('EXPLAIN (VERBOSE, FORMAT JSON, COSTS OFF) '
                                                     f'SELECT ({wanted}), ({stored}) FROM {target}')[0][0]
                                output = plan[0]['Plan']['Output']
                                equal = len(output) == 2 and output[0] == output[1]
                            except Exception:
                                reader.close()
                                reader.connect()
                    if not equal:
                        migrator.record_skipped('alter_generated_expression',
                                                f'{schema}.{table}.{name}; explicit migration required')
    finally:
        if connected:
            reader.close()
