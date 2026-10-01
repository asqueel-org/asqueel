"""Errors shared by database handles and their internal connections."""


class DatabaseClosedError(RuntimeError):
    """The calling thread's database state has been closed."""


class TransactionStateError(RuntimeError):
    """The current operation cannot proceed in this connection state."""


class DeferredCommitError(RuntimeError):
    """One or more errors deliberately queued for the commit boundary."""
