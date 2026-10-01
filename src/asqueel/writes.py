"""Database-level write orchestration; adapters only render and execute SQL."""
from collections.abc import Mapping

from .application_table import _copy, RecordNotFoundError
from .contracts import QueryResult


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
        """Insert a mapping or list of mappings without table triggers or commits."""
        table = self._write_table(table)
        if not isinstance(values, list):
            return self._insert(table, values, returning, ignore_partition=ignore_partition, raw=True)
        with self._write_operation():
            if not all(isinstance(record, Mapping) for record in values):
                raise TypeError('Raw insert values must be a mapping or a list of mappings')
            records = _copy(values)
            rows, rowcount, columns = [], 0, ()
            for record in records:
                result = self._insert(table, record, returning, ignore_partition=ignore_partition, raw=True)
                rows.extend(result.rows)
                rowcount += result.rowcount
                columns = result.columns
            return QueryResult(rows, rowcount, columns)

    def update(self, table, values, where=None, sqlparams=None, returning='*', *, ignore_partition=False):
        return self._update(self._write_table(table), values, where, sqlparams, returning, ignore_partition=ignore_partition)

    def raw_update(self, table, values, where=None, sqlparams=None, returning='*', *, ignore_partition=False):
        return self._update(self._write_table(table), values, where, sqlparams, returning, ignore_partition=ignore_partition, raw=True)

    def delete(self, table, record_or_pkey=None, *, where=None, sqlparams=None, returning='*', ignore_partition=False):
        return self._delete(self._write_table(table), record_or_pkey, where=where, sqlparams=sqlparams,
                            returning=returning, ignore_partition=ignore_partition)

    def raw_delete(self, table, record_or_pkey=None, *, where=None, sqlparams=None, returning='*', ignore_partition=False):
        return self._delete(self._write_table(table), record_or_pkey, where=where, sqlparams=sqlparams,
                            returning=returning, ignore_partition=ignore_partition, raw=True)

    def _direct_write(self, table, event, record, compiled, *, raw):
        self.onWriting(table, event, record, raw=raw)
        self.onExecutingWrite(table, event, record, raw=raw)
        result = self.execute(compiled() if callable(compiled) else compiled)
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

    def _update(self, table, values, where=None, sqlparams=None, returning='*', *, ignore_partition=False, raw=False):
        with self._write_operation():
            if not isinstance(values, Mapping):
                raise TypeError('Update values must be a mapping')
            record = _copy(dict(values))
            if where is None:
                where, sqlparams = table._key_selector(record, sqlparams)
            # Validate the caller's write predicate and values before acquiring locks.
            self.compiler.update(
                table.fullname, record, where, sqlparams, returning, ignore_partition=ignore_partition)
            with table._trigger_operation('update', record=record) as trigger:
                if raw:
                    return self._direct_write(table, 'U', record, lambda: self.compiler.update(
                        table.fullname, record, where, sqlparams, returning,
                        ignore_partition=ignore_partition), raw=True)
                old_record = table._locked_record(where, sqlparams, ignore_partition)
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

    def _delete(self, table, record_or_pkey=None, *, where=None, sqlparams=None, returning='*', ignore_partition=False, raw=False):
        with self._write_operation():
            by_key = where is None
            if by_key:
                if record_or_pkey is None:
                    raise ValueError('Delete requires a primary key, record, or explicit where')
                where, sqlparams = table._key_selector(record_or_pkey, sqlparams)
            compiled = self.compiler.delete(
                table.fullname, where, sqlparams, returning, ignore_partition=ignore_partition)
            if raw:
                record = _copy(record_or_pkey) if by_key else None
                if record is not None and not isinstance(record, Mapping):
                    keys = table.model.pkey
                    values = [record] if len(keys) == 1 else record
                    record = dict(zip(keys, values))
                with table._trigger_operation('delete', record=record):
                    return self._direct_write(table, 'D', record, compiled, raw=True)
            record = table._locked_record(where, sqlparams, ignore_partition)
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

