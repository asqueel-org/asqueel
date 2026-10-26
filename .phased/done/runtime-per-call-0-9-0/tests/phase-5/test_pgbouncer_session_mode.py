"""asqueel#56 acceptance: PostgreSQL behind pgbouncer in session mode.

Skipped when GNR_TEST_PGBOUNCER_DSN is not set.
"""
import pytest

pytestmark = pytest.mark.pgbouncer


def test_repeated_queries_work_in_one_session_and_in_a_second_one():
    # wf:contract: with conninfo = GNR_TEST_PGBOUNCER_DSN (skipped when unset), the same
    # wf:contract: parametrized query run ten times in one SessionDb returns the same rows
    # wf:contract: each time, past psycopg's prepare_threshold of 5; the same ten runs in a
    # wf:contract: second SessionDb, opened after the first is closed, return the same rows.
    pytest.fail('phase 5 pending')


def test_a_named_cursor_is_read_inside_its_transaction():
    # wf:contract: a query read through a cursorname (server-side) cursor in a SessionDb
    # wf:contract: behind pgbouncer returns all its rows before the commit.
    pytest.fail('phase 5 pending')


def test_a_named_cursor_read_after_commit_raises_the_driver_error():
    # wf:contract: the same named cursor read after the commit raises the psycopg error
    # wf:contract: (no WITH HOLD, adapters/postgres.py cursor); the test asserts that error
    # wf:contract: class, so a later WITH HOLD change is a visible decision.
    pytest.fail('phase 5 pending')
