"""Overridable write hooks of a table, as GenroPy TriggersMixin (fa35e5ad).

Reference gnr/sql/gnrsqltable/triggers.py:117-185 and table.py:92-120. The
base implementations do nothing: an application table overrides them. The
write cycle in db_write.py calls them in the GenroPy order.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .errors import EXCEPTIONS
from .model import _parse_row_policies


class TriggersMixin:
    """Table hooks called by the write cycle; every base hook is a no-op."""

    def trigger_onInserting(self, record):
        """Before the INSERT; changes to ``record`` reach the SQL."""

    def trigger_onInserted(self, record):
        """After the INSERT, in the same transaction."""

    def trigger_onUpdating(self, record, old_record=None):
        """Before the UPDATE; changes to ``record`` reach the SQL."""

    def trigger_onUpdated(self, record, old_record=None):
        """After the UPDATE, in the same transaction."""

    def trigger_onDeleting(self, record):
        """Before the related actions and the DELETE."""

    def trigger_onDeleted(self, record):
        """After the DELETE, in the same transaction."""

    def protect_update(self, record, old_record=None):
        """Raise ``self.exception('protect_update', ...)`` to refuse an update."""

    def protect_delete(self, record):
        """Raise ``self.exception('protect_delete', ...)`` to refuse a delete."""

    def protect_validate(self, record, old_record=None):
        """Raise ``self.exception('protect_validate', ...)`` to refuse the values."""

    def trigger_assignCounters(self, record=None, old_record=None):
        """Assign counter values before the INSERT or UPDATE."""

    def trigger_releaseCounters(self, record=None):
        """Release counter values after the DELETE."""

    def trigger_setTSNow(self, record, fldname, **kwargs):
        """sys_fields timestamp: aware UTC for a ``DHZ`` column, naive local otherwise."""
        if self.model.columns[fldname].dtype == 'DHZ':
            record[fldname] = datetime.now(timezone.utc)
        else:
            record[fldname] = datetime.now()

    def trigger_setCurrentUser(self, record, fldname, **kwargs):
        """sys_fields user: the ``user`` of the current environment."""
        record[fldname] = self.db.currentUser

    @property
    def draftField(self):
        return _parse_row_policies(self.model.attributes).draft_field

    @property
    def logicalDeletionField(self):
        return _parse_row_policies(self.model.attributes).logical_deletion_field

    def exception(self, exception, record=None, msg=None, **kwargs):
        """The exception named ``exception`` (or that class), ready to raise."""
        if isinstance(exception, str):
            name = exception
            exception = EXCEPTIONS.get(name)
            if exception is None:
                raise ValueError(f'Unknown exception name: {name!r}')
        rowcaption = ''
        if record:
            rowcaption = str(record.get(self.model.pkey) or '')
        return exception(msg, tablename=self.fullname, rowcaption=rowcaption, **kwargs)
