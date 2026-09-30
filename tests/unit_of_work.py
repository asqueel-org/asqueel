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
