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

from copy import deepcopy

from .application_table import RecordNotFoundError
from .common import sql_attribute_declared
from .model_source import require_write_capabilities


class WriteMixin:
    """Database-level write cycle; the table commands delegate to it."""

    def insert(self, tblobj, record, *, ignore_partition=False, **kwargs):
        require_write_capabilities(tblobj.model)
        with self._write_operation(), self._trigger_operation('insert', tblobj, record=record):
            tblobj._lock_behaviors()
            tblobj._check_column_changes(record)
            self.write_compiler._guard_partition(tblobj.model, record, self.environment.snapshot(),
                                                   insert=True, ignore_partition=ignore_partition)
            tblobj._insert_defaults(record)
            tblobj.checkPkey(record)
            tblobj.protect_validate(record)
            tblobj._doFieldTriggers('onInserting', record)
            prepared = deepcopy(record)
            tblobj.trigger_onInserting(record)
            tblobj.trigger_assignCounters(record=record)
            self._protect_draft(tblobj, record)
            tblobj._finish_behaviors(record, prepared)
            before_sql = deepcopy(record)
            self._write(tblobj, record, self.write_compiler.insert(
                tblobj.model, record, self.environment.snapshot(), ignore_partition=ignore_partition))
            tblobj._complete_linked_insert(record, before_sql, ignore_partition=ignore_partition)
            tblobj._doFieldTriggers('onInserted', record)
            tblobj.trigger_onInserted(record)

    def update(self, tblobj, record, old_record=None, pkey=None, *, ignore_partition=False, **kwargs):
        require_write_capabilities(tblobj.model)
        with self._write_operation(), self._trigger_operation(
                'update', tblobj, record=record, old_record=old_record):
            tblobj._lock_behaviors()
            if tblobj._behavior('hierarchical') is not None and old_record is None:
                raise tblobj.exception('standard', msg='Updating a hierarchical record requires old_record')
            active_partition = self.write_compiler._partition(tblobj.model, self.environment.snapshot(), ignore_partition)
            needs_snapshot = active_partition is not None or tblobj._behavior('hierarchical') is not None or any(
                column.attributes.get('readOnly') or column.attributes.get('unmodifiable')
                or sql_attribute_declared(column.attributes, 'generatedExpression')
                for column in tblobj.model.columns.values())
            if needs_snapshot:
                key = tblobj._record_key(old_record) if old_record else (
                    pkey if pkey is not None else tblobj._record_key(record))
                stored = tblobj._reread(key)
                if stored is None:
                    raise RecordNotFoundError(f'{tblobj.fullname}: no record to update')
                if old_record is None:
                    old_record = stored
                else:
                    old_record.update(stored)
            if old_record is not None:
                self.write_compiler._guard_partition(tblobj.model, old_record, self.environment.snapshot(),
                                                       ignore_partition=ignore_partition)
                self.currentTrigger.old_record = old_record
            original = deepcopy(old_record)
            tblobj._check_column_changes(record, original)
            tblobj.protect_update(record, old_record=old_record)
            tblobj.protect_validate(record, old_record=old_record)
            tblobj._doFieldTriggers('onUpdating', record, old_record=old_record)
            prepared = deepcopy(record)
            tblobj.trigger_onUpdating(record, old_record=old_record)
            # GnrDboTable.dbo_onUpdating ran protect_draft here, before the counters.
            self._protect_draft(tblobj, record)
            # GnrDboTable.dbo_onUpdating archived the cascade children here.
            ldf = tblobj.logicalDeletionField
            if ldf and old_record and record.get(ldf) != old_record.get(ldf):
                tblobj.archiveRelatedRecords(record, record.get(ldf))
            tblobj.trigger_assignCounters(record=record, old_record=old_record)
            tblobj._check_column_changes(record, original)
            tblobj._finish_behaviors(record, prepared, original)
            self._write(tblobj, record, self.write_compiler.update(
                tblobj.model, tblobj._sql_record(record), self.environment.snapshot(), pkey=pkey, old_record=original, ignore_partition=ignore_partition))
            tblobj.updateRelated(record, old_record=old_record)
            tblobj._doFieldTriggers('onUpdated', record, old_record=old_record)
            tblobj.trigger_onUpdated(record, old_record=old_record)

    def delete(self, tblobj, record, *, ignore_partition=False, **kwargs):
        require_write_capabilities(tblobj.model)
        with self._write_operation(), self._trigger_operation('delete', tblobj, record=record, old_record=deepcopy(record)):
            tblobj._lock_behaviors()
            original = deepcopy(record)
            if self.write_compiler._partition(tblobj.model, self.environment.snapshot(), ignore_partition) is not None:
                original = tblobj._reread(tblobj._record_key(record))
                if original is None:
                    raise RecordNotFoundError(f'{tblobj.fullname}: no record to delete')
                self.write_compiler._guard_partition(tblobj.model, original, self.environment.snapshot(),
                                                       ignore_partition=ignore_partition)
            self.currentTrigger.old_record = deepcopy(original)
            deletable = tblobj.model.attributes.get('deletable', True)
            if isinstance(deletable, str):
                raise ValueError(f'{tblobj.fullname}: deletable permission tags need the application')
            if not deletable:
                raise tblobj.exception('delete', record=record, msg='The records of this table cannot be deleted')
            tblobj.protect_delete(record)
            tblobj._doFieldTriggers('onDeleting', record)
            tblobj.trigger_onDeleting(record)
            tblobj.deleteRelated(original)
            cursor = self.execute(self.write_compiler.delete(tblobj.model, original, self.environment.snapshot(), ignore_partition=ignore_partition))
            rowcount = cursor.rowcount
            cursor.close()
            if rowcount != 1:
                raise RecordNotFoundError(f'{tblobj.fullname}: DELETE removed {rowcount} rows instead of 1')
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
        cursor = self.execute(compiled)
        rows = cursor.fetchall() if cursor.description is not None else []
        cursor.close()
        if rows:
            record.update(dict(rows[0]))
