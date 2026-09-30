# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Phase 21 contract — safe physical names and reproducible test setup."""
from pathlib import Path

from asqueel_migration.writers.mssql_writer import MssqlWriter
from asqueel_migration.writers.mysql_writer import MysqlWriter
from asqueel_migration.writers.pg_writer import PgWriter
from asqueel_migration.writers.sqlite_writer import SqliteWriter


ROOT = Path(__file__).resolve().parents[1]
WRITERS = (PgWriter, MysqlWriter, MssqlWriter, SqliteWriter)


def test_authored_index_names_are_dialect_quoted_at_the_writer_boundary():
    # wf:contract: reserved, punctuated, mixed-case and embedded-quote index names
    # wf:contract: are quoted and escaped by each SQL dialect writer; no recipe
    # wf:contract: restriction or asqueel renderer workaround replaces them.
    for writer_class in WRITERS:
        writer = writer_class()
        for name in ("select", "ix-with-dash", "MixedCase", 'ix"quoted'):
            quoted = writer.quote_identifier(name)
            sql = writer.create_index_sql(
                "schema", "table", {"column": None}, index_name=name,
            )
            assert quoted in sql


def test_documented_development_extra_can_collect_the_complete_suite():
    # wf:contract: the README development command installs every dependency that
    # wf:contract: tests/conftest.py imports at collection, including migration
    # wf:contract: validation and PostgreSQL support.
    metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert 'asqueel-migration[postgresql,validation]>=0.1.0' in metadata
    assert (
        'pip install -e "../asqueel-migration[postgresql,validation]" '
        '-e ".[dev]"'
    ) in readme


def test_delivery_record_does_not_claim_an_unpublished_release():
    # wf:contract: delivery.md names exact asqueel-migration commits and the
    # wf:contract: remaining PR/release/minimum-version actions; pyproject does
    # wf:contract: not invent a version that cannot be resolved publicly.
    delivery = (ROOT / "docs/delivery.md").read_text(encoding="utf-8")
    assert "dced81ca6e601d067a647727d4d329b63da2bb70" in delivery
    assert "2cb51a45c118a8d601d2d43da752fef792cc966c" in delivery
    assert "bb3f425b229d9c4c988e308e164faa4c1b54fb7e" in delivery
    assert "#8" in delivery and "open" in delivery
    assert "No publish, pull request, merge or release action" in delivery
    assert "no matching `asqueel-migration` distribution" in delivery
    assert "asqueel-migration>=0.1.1" not in (
        ROOT / "pyproject.toml"
    ).read_text(encoding="utf-8")
