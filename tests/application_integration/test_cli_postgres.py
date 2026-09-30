"""CLI acceptance: missing DB -> migrated schemas -> Python/REPL I/O -> empty plan."""
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
import pytest

from asqueel import build_database
from asqueel.cli import main
from tests.native_support import postgres_dsn
from tests.documentation.test_examples import python_blocks

pytestmark = pytest.mark.postgresql
EXAMPLE = Path(__file__).resolve().parents[2] / 'examples' / 'two_schemas'


def test_cli_creates_database_and_reuses_registered_configuration(tmp_path, monkeypatch, capsys):
    name = 'asq_cli_' + uuid4().hex
    params = conninfo_to_dict(postgres_dsn())
    monkeypatch.setenv('ASQUEEL_HOME', str(tmp_path / 'registry'))
    for key, env in [('host', 'PGHOST'), ('port', 'PGPORT'), ('user', 'PGUSER'),
                     ('password', 'PGPASSWORD')]:
        if key in params:
            monkeypatch.setenv(env, params[key])
        else:
            monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv('PGDATABASE', name)
    with psycopg.connect(postgres_dsn(), autocommit=True) as admin:
        try:
            assert main(['register', 'gestionale', str(EXAMPLE)]) == 0
            monkeypatch.chdir(tmp_path)
            assert main(['check', 'gestionale']) == 0
            assert main(['db', 'plan', 'gestionale']) == 0
            output = capsys.readouterr()
            assert f'CREATE DATABASE "{name}"' in output.out
            assert not admin.execute('SELECT 1 FROM pg_database WHERE datname=%s', (name,)).fetchone()
            assert main(['db', 'apply', 'gestionale']) == 0, capsys.readouterr()
            assert admin.execute('SELECT 1 FROM pg_database WHERE datname=%s', (name,)).fetchone()
            # Execute the published walkthrough verbatim against the freshly migrated DB.
            snippet = python_blocks('two-schemas.md')[0]
            exec(compile(snippet, 'two-schemas.md:python-0', 'exec'), {})
            def console(**kwargs):
                db = kwargs['local']['db']
                assert db.table('identity.user').query().fetch()[0]['username'] == 'ada'
                db.table('sales.customer').insert({'id': 2, 'name': 'Committed from console'})
                db.commit()
                db.table('sales.customer').insert({'id': 3, 'name': 'Pending on exit'})
            monkeypatch.setattr('asqueel.cli.code.interact', console)
            assert main(['shell', 'gestionale']) == 0
            with build_database('gestionale') as db:
                rows = db.table('sales.customer').query(columns='$id', order_by='$id').fetch()
                assert [row['id'] for row in rows] == [1, 2]
            capsys.readouterr()
            assert main(['db', 'plan', 'gestionale']) == 0
            assert capsys.readouterr().out.strip() == 'No changes.'
            assert main(['db', 'apply', 'gestionale']) == 0
            assert capsys.readouterr().out.strip() == 'No changes.'
            with psycopg.connect(**{**params, 'dbname': name}, autocommit=True) as target:
                target.execute('CREATE SCHEMA unrelated')
                target.execute('CREATE TABLE unrelated.keep_me (id integer)')
                target.execute('CREATE TABLE sales.obsolete (id integer)')
                target.execute('ALTER TABLE sales.customer ADD COLUMN obsolete_note text')
                assert main(['db', 'plan', 'gestionale']) == 0
                assert 'DROP TABLE' not in capsys.readouterr().out
                assert main(['db', 'plan', 'gestionale', '--allow-removals']) == 0
                removal_plan = capsys.readouterr().out
                assert 'DROP COLUMN "obsolete_note"' in removal_plan and 'keep_me' not in removal_plan
                assert target.execute("SELECT to_regclass('sales.obsolete')").fetchone()[0]
                assert main(['db', 'apply', 'gestionale', '--allow-removals']) == 0
                assert not target.execute("SELECT 1 FROM information_schema.columns WHERE "
                                          "table_schema='sales' AND table_name='customer' "
                                          "AND column_name='obsolete_note'").fetchone()
                # The existing migrator deliberately never drops whole tables.
                assert target.execute("SELECT to_regclass('sales.obsolete')").fetchone()[0]
                assert target.execute("SELECT to_regclass('unrelated.keep_me')").fetchone()[0]
        finally:
            admin.execute(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(name)))
