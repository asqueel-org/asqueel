"""An application creates and evolves its tables from Python, without the CLI."""
import sqlite3

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
