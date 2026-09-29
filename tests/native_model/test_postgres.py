"""Run with GENRO_SQL_TEST_DSN against a disposable PostgreSQL database."""
import uuid

import pytest

from genro_sql.importers import inspect_postgres
from tests.native_support import postgres_dsn

pytestmark = pytest.mark.postgresql


def test_real_catalog_preserves_composite_keys_defaults_and_index_definition(monkeypatch):
    dsn = postgres_dsn()
    psycopg = pytest.importorskip('psycopg')
    from psycopg import sql
    schema = 'v1_model_' + uuid.uuid4().hex[:12]
    with psycopg.connect(dsn) as connection:
        connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        connection.execute(sql.SQL('''CREATE TABLE {}.parent (
            first integer, second integer, label text DEFAULT 'hello',
            PRIMARY KEY(first,second))''').format(sql.Identifier(schema)))
        connection.execute(sql.SQL('''CREATE TABLE {}.child (
            id integer PRIMARY KEY, first integer, second integer,
            CONSTRAINT pair_fk FOREIGN KEY(first,second) REFERENCES {}.parent(first,second))'''
        ).format(sql.Identifier(schema), sql.Identifier(schema)))
        connection.execute(sql.SQL('CREATE INDEX ordered_label ON {}.parent (label DESC) WHERE label IS NOT NULL'
                                   ).format(sql.Identifier(schema)))
        connection.execute(sql.SQL('CREATE VIEW {}.labels AS SELECT label FROM {}.parent'
                                   ).format(sql.Identifier(schema), sql.Identifier(schema)))
        overlay = {f'{schema}.parent.label': {'label': 'Caption'}}
        result = inspect_postgres(connection, [schema], ui=overlay)
        parent = result.model.table('parent')
        assert parent.pkey == ('first', 'second')
        assert parent.columns['label'].attributes['default'] == "'hello'::text"
        assert parent.columns['label'].ui['label'] == 'Caption'
        assert any('DESC' in i['definition'] and i['predicate'] for i in parent.attributes['indexes'])
        relation = result.model.table('child').relations['pair_fk']
        assert relation.columns == relation.target_columns == ('first', 'second')
        assert any('labels' in w and 'unmanaged' in w for w in result.warnings)
        assert inspect_postgres(connection, [schema], ui=overlay).model == result.model
        from genro_sql.projection import to_physical_builder
        from genro_sql import SqlMigrationRenderer
        from genro_sql.contracts import UnsupportedFeatureError
        assert result.model.warnings == result.warnings
        with pytest.raises(UnsupportedFeatureError, match='import warnings'):
            to_physical_builder(result.model, allow_constraint_rename=True)
        connection.execute(sql.SQL('DROP VIEW {}.labels').format(sql.Identifier(schema)))
        result = inspect_postgres(connection, [schema], ui=overlay)
        with pytest.raises(UnsupportedFeatureError, match='constraint names'):
            to_physical_builder(result.model)
        physical = to_physical_builder(result.model, allow_constraint_rename=True)
        structure = SqlMigrationRenderer(physical).render()
        tables = structure['root']['schemas'][schema]['tables']
        assert set(tables) == {'parent', 'child'}
        assert tables['child']['relations']
        assert not tables['child']['indexes']
        assert any(i['attributes']['columns'].get('label') == 'DESC'
                   for i in tables['parent']['indexes'].values())
        assert parent.columns['first'].dtype == 'I'
        from genro_sqlmigration import PgDatabase, SqlMigrator
        from genro_sqlmigration.readers.pg_reader import PgReader
        database = PgDatabase(connection.info.get_parameters(), application_schemas=[schema])
        reader = PgReader()
        reader._conn = connection
        monkeypatch.setattr(reader, 'connect', lambda: None)
        monkeypatch.setattr(reader, 'close', lambda: None)
        database.adapter._reader = reader
        migrator = SqlMigrator(database, ignore_constraint_name=True, removeDisabled=False)
        migrator.ormStructure = structure
        migrator.prepareMigrationCommands()
        assert not migrator.getChanges(), list(migrator.diff)
        connection.rollback()  # All objects belong to this isolated transaction.


@pytest.mark.parametrize(('ddl', 'error'), [
    ('CREATE TABLE {schema}.t(label text COLLATE "C")', 'custom column collation'),
    ('CREATE TABLE {schema}.t(id serial)', 'import warnings'),
    ("CREATE TABLE {schema}.parent(tenant integer,id integer,PRIMARY KEY(tenant,id)); "
     "CREATE TABLE {schema}.child(tenant integer NOT NULL,parent_id integer,"
     "FOREIGN KEY(tenant,parent_id) REFERENCES {schema}.parent(tenant,id) "
     "ON DELETE SET NULL(parent_id))", 'column subset'),
    ('CREATE TABLE {schema}.t(id integer UNIQUE WITH(fillfactor=70))', 'advanced constraint index'),
    ('CREATE TABLE {schema}.t(id integer); ALTER TABLE {schema}.t ENABLE ROW LEVEL SECURITY', 'import warnings'),
])
def test_unsupported_catalog_semantics_cannot_become_a_partial_migration(ddl, error):
    import psycopg
    from psycopg import sql
    from genro_sql.projection import to_physical_builder
    from genro_sql.contracts import UnsupportedFeatureError
    schema = 'v1_model_' + uuid.uuid4().hex[:12]
    with psycopg.connect(postgres_dsn()) as connection:
        connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        connection.execute(sql.SQL(ddl).format(schema=sql.Identifier(schema)))
        result = inspect_postgres(connection, [schema])
        assert result.model.tables  # Still usable for reading.
        with pytest.raises(UnsupportedFeatureError, match=error):
            to_physical_builder(result.model, allow_constraint_rename=True)
        connection.rollback()


def test_missing_requested_schema_blocks_projection():
    import psycopg
    from genro_sql.projection import to_physical_builder
    from genro_sql.contracts import UnsupportedFeatureError
    schema = 'v1_model_missing_' + uuid.uuid4().hex[:12]
    with psycopg.connect(postgres_dsn()) as connection:
        result = inspect_postgres(connection, [schema])
        assert result.model.warnings == result.warnings
        assert 'does not exist' in result.warnings[0]
        with pytest.raises(UnsupportedFeatureError, match='import warnings'):
            to_physical_builder(result.model)
