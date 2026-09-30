"""Database-level write orchestration; adapters only render and execute SQL."""
from collections.abc import Mapping

from .application_table import _copy, RecordNotFoundError


class WriteMixin:
    def onWriting(self, table, event, record, old_record=None, *, raw=False):
        """Extension point before table hooks; raw bypasses table hooks only."""

    def onExecutingWrite(self, table, event, record, old_record=None, *, raw=False):
        """Extension point after before-hooks and immediately before SQL."""

    def _onDbChange(self, table, event, record, old_record=None, *, _raw=False):
        """Change tracking for ordinary and raw writes, before after-hooks."""

    def onWritten(self, table, event, record, old_record=None, *, raw=False):
        """Extension point after the entire write cycle, still before commit."""

    def _write_table(self, table):
        table = self.table(table) if isinstance(table, str) else table
        if table.db is not self:
            raise ValueError('The table belongs to another database')
        return table

    def insert(self, table, values, returning='*', *, ignore_partition=False):
        return self._insert(self._write_table(table), values, returning, ignore_partition=ignore_partition)

    def raw_insert(self, table, values, returning='*', *, ignore_partition=False):
        return self._insert(self._write_table(table), values, returning, ignore_partition=ignore_partition, raw=True)

    def update(self, table, values, where=None, params=None, returning='*', *, ignore_partition=False):
        return self._update(self._write_table(table), values, where, params, returning, ignore_partition=ignore_partition)

    def raw_update(self, table, values, where=None, params=None, returning='*', *, ignore_partition=False):
        return self._update(self._write_table(table), values, where, params, returning, ignore_partition=ignore_partition, raw=True)

    def delete(self, table, record_or_pkey=None, *, where=None, params=None, returning='*', ignore_partition=False):
        return self._delete(self._write_table(table), record_or_pkey, where=where, params=params,
                            returning=returning, ignore_partition=ignore_partition)

    def raw_delete(self, table, record_or_pkey=None, *, where=None, params=None, returning='*', ignore_partition=False):
        return self._delete(self._write_table(table), record_or_pkey, where=where, params=params,
                            returning=returning, ignore_partition=ignore_partition, raw=True)

    def _needs_record(self, table, operation, raw):
        shared = any(getattr(type(self), name) is not getattr(WriteMixin, name) for name in
                     ('onWriting', 'onExecutingWrite', '_onDbChange', 'onWritten'))
        return shared or (not raw and table._has_write_hooks(operation))

    def _direct_write(self, table, event, record, compiled, *, raw):
        self.onWriting(table, event, record, raw=raw)
        self.onExecutingWrite(table, event, record, raw=raw)
        result = self.execute(compiled)
        self._onDbChange(table, event, record, _raw=raw)
        self.onWritten(table, event, record, raw=raw)
        return result

    def _insert(self, table, values, returning='*', *, ignore_partition=False, raw=False):
        with self._write_operation():
            if not isinstance(values, Mapping):
                raise TypeError('Insert values must be a mapping')
            record = _copy(dict(values))
            with table._trigger_operation('insert', record=record):
                self.onWriting(table, 'I', record, raw=raw)
                if not raw:
                    table.trigger_onInserting(record)
                self.onExecutingWrite(table, 'I', record, raw=raw)
                result = self.execute(self.compiler.insert(
                    table.fullname, record, returning, ignore_partition=ignore_partition))
                table._overlay_returned(record, result)
                self._onDbChange(table, 'I', record, _raw=raw)
                if not raw:
                    table.trigger_onInserted(record)
                self.onWritten(table, 'I', record, raw=raw)
                return result

    def _update(self, table, values, where=None, params=None, returning='*', *, ignore_partition=False, raw=False):
        with self._write_operation():
            if not isinstance(values, Mapping):
                raise TypeError('Update values must be a mapping')
            record = _copy(dict(values))
            if where is None:
                where, params = table._key_selector(record, params)
            # Validate the caller's write predicate and values before acquiring locks.
            compiled = self.compiler.update(
                table.fullname, record, where, params, returning, ignore_partition=ignore_partition)
            with table._trigger_operation('update', record=record) as trigger:
                if not self._needs_record(table, 'update', raw):
                    return self._direct_write(table, 'U', record, compiled, raw=raw)
                old_record = table._locked_record(where, params, ignore_partition)
                key_where, key_params = table._key_selector(old_record)
                merged = _copy(old_record)
                merged.update(record)
                if trigger is not None:
                    trigger.record = merged
                    trigger.old_record = old_record
                self.onWriting(table, 'U', merged, old_record=_copy(old_record), raw=raw)
                if not raw:
                    table.trigger_onUpdating(merged, old_record=_copy(old_record))
                self.onExecutingWrite(table, 'U', merged, old_record=_copy(old_record), raw=raw)
                result = self.execute(self.compiler.update(
                    table.fullname, merged, key_where, key_params, returning,
                    ignore_partition=ignore_partition))
                if result.rowcount != 1:
                    raise RecordNotFoundError('Locked update did not affect exactly one record')
                table._overlay_returned(merged, result)
                self._onDbChange(table, 'U', merged, old_record=_copy(old_record), _raw=raw)
                if not raw:
                    table.trigger_onUpdated(merged, old_record=_copy(old_record))
                self.onWritten(table, 'U', merged, old_record=_copy(old_record), raw=raw)
                return result

    def _delete(self, table, record_or_pkey=None, *, where=None, params=None, returning='*', ignore_partition=False, raw=False):
        with self._write_operation():
            if where is None:
                if record_or_pkey is None:
                    raise ValueError('Delete requires a primary key, record, or explicit where')
                where, params = table._key_selector(record_or_pkey, params)
            compiled = self.compiler.delete(
                table.fullname, where, params, returning, ignore_partition=ignore_partition)
            if not self._needs_record(table, 'delete', raw):
                with table._trigger_operation('delete', record=record_or_pkey):
                    return self._direct_write(table, 'D', record_or_pkey, compiled, raw=raw)
            record = table._locked_record(where, params, ignore_partition)
            key_where, key_params = table._key_selector(record)
            with table._trigger_operation('delete', record=record):
                self.onWriting(table, 'D', record, raw=raw)
                if not raw:
                    table.trigger_onDeleting(record)
                self.onExecutingWrite(table, 'D', record, raw=raw)
                result = self.execute(self.compiler.delete(
                    table.fullname, key_where, key_params, returning,
                    ignore_partition=ignore_partition))
                if result.rowcount != 1:
                    raise RecordNotFoundError('Locked delete did not affect exactly one record')
                self._onDbChange(table, 'D', record, _raw=raw)
                if not raw:
                    table.trigger_onDeleted(record)
                self.onWritten(table, 'D', record, raw=raw)
                return result

