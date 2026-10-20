"""Test setup helper using only explicit public completion commands."""
from contextlib import contextmanager


@contextmanager
def completed(db):
    try:
        yield db
        db.commit()
    except BaseException as error:
        try:
            db.rollback()
        except BaseException as cleanup:
            error.add_note(f'Test cleanup failed: {type(cleanup).__name__}')
            raise error from cleanup
        raise


class FakeCursor:
    """A driver cursor over fixed rows (dicts), returned by the fake adapters' execute."""

    def __init__(self, rows=(), rowcount=None):
        rows = [dict(row) for row in rows]
        self.description = [(name,) for name in rows[0]] if rows else None
        self.rowcount = len(rows) if rowcount is None else rowcount
        self.arraysize = 1
        self._rows = [tuple(row.values()) for row in rows]

    def fetchall(self):
        rows, self._rows = self._rows, []
        return rows

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchmany(self, size=None):
        size = size or self.arraysize
        rows, self._rows = self._rows[:size], self._rows[size:]
        return rows

    def close(self):
        pass
