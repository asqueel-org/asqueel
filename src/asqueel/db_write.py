"""The insert, update and delete cycle, as GenroPy WriteMixin (fa35e5ad).

Reference gnr/sql/gnrsql/write.py:133-319. The steps and their order are the
legacy ones. Differences decided in the write-cycle plan:
- no _onDbChange (totalizers, change log and NOTIFY are out of scope);
- no external package triggers yet (customizations are postponed);
- no dbo_* hooks: protect_draft is called directly, in the legacy position;
- RETURNING values decided by the database are written into the record;
- a DELETE must remove exactly one row;
- a Python error during the cycle makes the connection rollback-only.
"""
from __future__ import annotations

from .application_table import RecordNotFoundError


class WriteMixin:
    """Database-level write cycle; the table commands delegate to it."""

    def insert(self, tblobj, record, **kwargs):
        with self._write_operation(), self._trigger_operation('insert', tblobj, record=record):
            tblobj.checkPkey(record)
            tblobj.protect_validate(record)
            tblobj._doFieldTriggers('onInserting', record)
            tblobj.trigger_onInserting(record)
            tblobj.trigger_assignCounters(record=record)
            self._protect_draft(tblobj, record)
            self._write(tblobj, record, self.write_compiler.insert(
                tblobj.model, record, self.environment.snapshot()))
            tblobj._doFieldTriggers('onInserted', record)
            tblobj.trigger_onInserted(record)

    def update(self, tblobj, record, old_record=None, pkey=None, **kwargs):
        with self._write_operation(), self._trigger_operation(
                'update', tblobj, record=record, old_record=old_record):
            tblobj.protect_update(record, old_record=old_record)
            tblobj.protect_validate(record, old_record=old_record)
            tblobj._doFieldTriggers('onUpdating', record, old_record=old_record)
            tblobj.trigger_onUpdating(record, old_record=old_record)
            # GnrDboTable.dbo_onUpdating ran protect_draft here, before the counters.
            self._protect_draft(tblobj, record)
            tblobj.trigger_assignCounters(record=record, old_record=old_record)
            self._write(tblobj, record, self.write_compiler.update(
                tblobj.model, record, self.environment.snapshot(), pkey=pkey, old_record=old_record))
            tblobj.updateRelated(record, old_record=old_record)
            tblobj._doFieldTriggers('onUpdated', record, old_record=old_record)
            tblobj.trigger_onUpdated(record, old_record=old_record)

    def delete(self, tblobj, record, **kwargs):
        with self._write_operation(), self._trigger_operation('delete', tblobj, record=record):
            deletable = tblobj.model.attributes.get('deletable', True)
            if isinstance(deletable, str):
                raise ValueError(f'{tblobj.fullname}: deletable permission tags need the application')
            if not deletable:
                raise tblobj.exception('delete', record=record, msg='The records of this table cannot be deleted')
            tblobj.protect_delete(record)
            tblobj._doFieldTriggers('onDeleting', record)
            tblobj.trigger_onDeleting(record)
            tblobj.deleteRelated(record)
            result = self.execute(self.write_compiler.delete(tblobj.model, record, self.environment.snapshot()))
            if result.rowcount != 1:
                raise RecordNotFoundError(f'{tblobj.fullname}: DELETE removed {result.rowcount} rows instead of 1')
            tblobj._doFieldTriggers('onDeleted', record)
            tblobj.trigger_onDeleted(record)
            tblobj.trigger_releaseCounters(record)

    @staticmethod
    def _protect_draft(tblobj, record):
        draft_field = tblobj.draftField
        protect_draft = getattr(type(tblobj), 'protect_draft', None)
        if draft_field and protect_draft is not None:
            record[draft_field] = protect_draft(tblobj, record)

    def _write(self, tblobj, record, compiled):
        result = self.execute(compiled)
        if result.rows:
            record.update(dict(result.rows[0]))
        return result
