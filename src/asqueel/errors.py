"""Errors shared by database handles and their internal connections."""


class TransactionStateError(RuntimeError):
    """The current operation cannot proceed in this connection state."""


class DeferredCommitError(RuntimeError):
    """One or more errors deliberately queued for the commit boundary."""


class MigrationError(ValueError):
    """A migration cannot run, or ran and left differences; the message says which.

    The message carries DDL and backend warnings, never connection credentials.
    """


# ----------------------------------------------------------------------
#  Write refusals meant for the user (GenroPy gnrsqltable EXCEPTIONS)
# ----------------------------------------------------------------------
# These are business outcomes: a precise message for the person using the
# application. Programming or state problems stay ordinary errors
# (ValueError, TypeError, RecordNotFoundError, TransactionStateError).

class RecordException(Exception):
    """A write refused by the application's rules, with a message for the user."""

    caption = '%(msg)s'

    def __init__(self, msg=None, *, tablename=None, rowcaption=None, **msgargs):
        self.msg = msg or ''
        self.tablename = tablename
        self.rowcaption = rowcaption or ''
        self.msgargs = msgargs
        super().__init__(str(self))

    def __str__(self):
        args = dict(self.msgargs, tablename=self.tablename, rowcaption=self.rowcaption)
        msg = self.msg % args if args and '%(' in self.msg else self.msg
        return self.caption % dict(args, msg=msg)


class SaveException(RecordException):
    caption = 'The record %(rowcaption)s in table %(tablename)s cannot be saved: %(msg)s'


class DeleteException(RecordException):
    caption = 'The record %(rowcaption)s in table %(tablename)s cannot be deleted: %(msg)s'


class ProtectUpdateException(RecordException):
    caption = 'The record %(rowcaption)s in table %(tablename)s is not updatable: %(msg)s'


class ProtectDeleteException(RecordException):
    caption = 'The record %(rowcaption)s in table %(tablename)s is not deletable: %(msg)s'


class ProtectValidateException(RecordException):
    caption = 'The record %(rowcaption)s in table %(tablename)s contains invalid data: %(msg)s'


class BusinessLogicException(RecordException):
    caption = 'The requested operation violates the internal business logic: %(msg)s'


#: Names used by ``table.exception(name, ...)``, as in GenroPy.
EXCEPTIONS = {
    'save': SaveException,
    'delete': DeleteException,
    'protect_update': ProtectUpdateException,
    'protect_delete': ProtectDeleteException,
    'protect_validate': ProtectValidateException,
    'business_logic': BusinessLogicException,
    'standard': RecordException,
}
