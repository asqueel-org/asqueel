"""An application creates and evolves its tables from Python, without the CLI."""
import sqlite3
import sys

import pytest

from asqueel import AsqueelDb, MigrationError, SqlDatabaseConfig
from tests.application_config.test_mounted_grammar import mounted_node


def recipe(path, name_dtype='T'):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            db = root.db()
            db.connection(name=str(path), implementation='sqlite')
            columns = db.schemas().schema('app').tables().table('item', pkey='id').columns()
            columns.column('id', dtype='L')
            columns.column('name', dtype=name_dtype)
    return Recipe


def item_columns(path):
    connection = sqlite3.connect(path.parent / f'{path.stem}_app.db')
    try:
        return [(row[1], row[2]) for row in connection.execute('PRAGMA table_info(item)')]
    finally:
        connection.close()


def test_plan_changes_nothing_and_migrate_creates_the_tables(tmp_path):
    path = tmp_path / 'sample.db'
    db = AsqueelDb(recipe(path))
    try:
        plan = db.migration_plan()
        assert 'CREATE TABLE' in plan.commands
        assert plan.skipped == ()
        assert db.migration_plan().commands == plan.commands
        applied = db.migrate()
        assert applied.commands == plan.commands
        assert db.migration_plan().empty
        db.table('app.item').insert({'id': 1, 'name': 'first'})
        db.commit()
        assert db.table('app.item').query(columns='$id, $name').fetch() == [{'id': 1, 'name': 'first'}]
    finally:
        db.close()


def test_migrate_on_an_up_to_date_database_returns_an_empty_plan(tmp_path):
    db = AsqueelDb(recipe(tmp_path / 'sample.db'))
    try:
        db.migrate()
        assert db.migrate().empty
    finally:
        db.close()


def test_a_database_declared_in_a_host_configuration_migrates(tmp_path):
    path = tmp_path / 'chat.db'
    db = AsqueelDb(mounted_node(path))
    try:
        db.migrate()
        db.table('chat.message').insert({'id': 1, 'text': 'ciao'})
        db.commit()
        assert db.table('chat.message').query(columns='$text').fetch() == [{'text': 'ciao'}]
    finally:
        db.close()


def test_a_change_sqlite_cannot_apply_is_refused_before_any_ddl(tmp_path):
    path = tmp_path / 'sample.db'
    first = AsqueelDb(recipe(path))
    try:
        first.migrate()
    finally:
        first.close()
    changed = AsqueelDb(recipe(path, name_dtype='L'))
    try:
        plan = changed.migration_plan()
        assert plan.skipped
        assert all(skipped in plan.warnings for skipped in plan.skipped)
        with pytest.raises(MigrationError, match='cannot apply'):
            changed.migrate()
    finally:
        changed.close()
    assert ('name', 'TEXT') in item_columns(path)


def test_an_in_memory_sqlite_database_cannot_be_migrated():
    db = AsqueelDb(recipe(':memory:'))
    try:
        with pytest.raises(MigrationError, match='persistent SQLite files'):
            db.migration_plan()
    finally:
        db.close()


def test_a_model_without_tables_cannot_be_migrated(tmp_path):
    class Empty(SqlDatabaseConfig):
        def main(self, root):
            db = root.db()
            db.connection(name=str(tmp_path / 'empty.db'), implementation='sqlite')
            db.schemas().schema('app')
    db = AsqueelDb(Empty)
    try:
        with pytest.raises(MigrationError, match='nonempty managed schema'):
            db.migration_plan()
    finally:
        db.close()


def test_a_legacy_connection_without_a_database_name_cannot_be_migrated():
    class Unnamed(SqlDatabaseConfig):
        def main(self, root):
            root.db(implementation='sqlite').schemas().schema('app').tables().table(
                'item', pkey='id').columns().column('id', dtype='L')
    db = AsqueelDb(Unnamed)
    try:
        with pytest.raises(MigrationError, match='Declare connection.name'):
            db.migration_plan()
    finally:
        db.close()


CONFIGURE = '''
from asqueel import SqlDatabaseConfig


class Recipe(SqlDatabaseConfig):
    def main(self, root):
        db = root.db()
        db.connection(name={path!r}, implementation='sqlite')
        columns = db.schemas().schema('app').tables().table('item', pkey='id').columns()
        columns.column('id', dtype='L')
        columns.column('name', dtype={dtype!r})
'''


def test_the_cli_refuses_a_skipped_change_and_names_it(tmp_path, capsys):
    from asqueel.cli import main
    path = tmp_path / 'sample.db'
    recipe_file = tmp_path / 'configure.py'
    recipe_file.write_text(CONFIGURE.format(path=str(path), dtype='T'))
    assert main(['db', 'apply', '--config', str(recipe_file)]) == 0
    # A second file: rewriting the first one in the same second can reuse its cached bytecode.
    changed_file = tmp_path / 'changed.py'
    changed_file.write_text(CONFIGURE.format(path=str(path), dtype='L'))
    capsys.readouterr()
    assert main(['db', 'plan', '--config', str(changed_file)]) == 0
    assert "Warning: unsupported 'alter_column_type'" in capsys.readouterr().err
    assert main(['db', 'apply', '--config', str(changed_file)]) == 1
    assert 'cannot apply these changes' in capsys.readouterr().err
    assert ('name', 'TEXT') in item_columns(path)


@pytest.mark.parametrize('module, implementation, hint', [
    ('asqueel_migration', 'sqlite', 'Install asqueel[migration]'),
    ('psycopg', 'postgresql', 'Install asqueel[postgresql]'),
])
def test_the_cli_names_the_missing_extra(tmp_path, monkeypatch, capsys, module, implementation, hint):
    from asqueel.cli import main
    recipe_file = tmp_path / 'configure.py'
    recipe_file.write_text(CONFIGURE.format(path=str(tmp_path / 'sample.db'), dtype='T').replace(
        "implementation='sqlite'", f"implementation={implementation!r}"))
    # The extra is not installed: Python finds None in sys.modules and refuses the import.
    monkeypatch.delitem(sys.modules, 'asqueel.migration', raising=False)
    monkeypatch.setitem(sys.modules, module, None)
    assert main(['db', 'plan', '--config', str(recipe_file)]) == 1
    assert hint in capsys.readouterr().err
