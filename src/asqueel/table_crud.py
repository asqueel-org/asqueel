"""Table write commands, as GenroPy CrudMixin (fa35e5ad).

Reference gnr/sql/gnrsqltable/crud.py:53-227 and 684-699, record.py:620-632,
utils.py:75-134. The commands return the caller's record, modified in place;
the cycle itself runs in db_write.WriteMixin.

Differences from the legacy, decided in the write-cycle plan:
- ``updateRelated`` continues with the next relation when a key did not
  change (genropy#1686) and refuses with ``save`` (genropy#1687);
- ``delete(dict)`` reloads with a lock only an incomplete dict;
- generated UUIDs come from ``genro_toolbox.uid.get_uuid``.
"""
from __future__ import annotations

import json

from genro_toolbox.uid import get_uuid

from .common import split_names

_INTEGER_DTYPES = frozenset({'L', 'I', 'R'})
_UUID_DTYPES = frozenset({'T', 'A', 'C'})
_FIELD_EVENTS = ('onInserting', 'onUpdating', 'onDeleting', 'onInserted', 'onUpdated', 'onDeleted')


class CrudMixin:
    """insert, update, delete and the related-record actions of a table."""

    # ------------------------------------------------------------------
    #  Commands
    # ------------------------------------------------------------------

    def insert(self, record, **kwargs):
        """Insert a single record and return it, modified by the cycle."""
        self.db.insert(self, record, **kwargs)
        return record

    def update(self, record, old_record=None, pkey=None, **kwargs):
        """Update a single record and return it.

        The key of the WHERE comes from ``old_record``, then ``pkey``, then the
        record; ``old_record`` is never read from the database.
        """
        if old_record and not pkey:
            pkey = old_record.get(self.model.pkey)
        if record.get(self.model.pkey) == pkey:
            pkey = None
        self.db.update(self, record, old_record=old_record, pkey=pkey, **kwargs)
        return record

    def delete(self, record, **kwargs):
        """Delete a single record: a key string, or a dict.

        A missing key string returns without error. A dict lacking physical
        columns is reloaded with a lock before the cycle.
        """
        if isinstance(record, str):
            record = self._reread(record, ignoreMissing=True)
            if record is None:
                return
        elif not set(self.model.columns) <= set(record):
            keys = self.pkeys
            key = record[keys[0]] if len(keys) == 1 else tuple(record[name] for name in keys)
            record = self._reread(key)
        self.db.delete(self, record, **kwargs)

    def _reread(self, pkey, ignoreMissing=False):
        """The complete row of ``pkey``, locked, outside the draft/logical-delete/partition filters."""
        where, sqlparams = self._key_selector(pkey)
        columns = ','.join('$' + name for name in self.model.columns)
        row = self.query(columns=columns, where=where, sqlparams=sqlparams, for_update=True,
                         exclude_draft=False, exclude_logical_deleted=False, ignore_partition=True,
                         bagFields=True).fetchRecord(ignoreMissing=ignoreMissing)
        return None if row is None else dict(row)

    # ------------------------------------------------------------------
    #  Keys
    # ------------------------------------------------------------------

    @property
    def pkeys(self):
        """Physical key columns: the components of a composite key, else the key."""
        return self.db.write_compiler.pkeys(self.model)

    def checkPkey(self, record):
        """Assign a generated key when the key is None or ''; True if assigned."""
        pkey = self.model.pkey
        if record.get(pkey) not in (None, ''):
            return False
        value = self.newPkeyValue(record=record)
        if value is not None:
            record[pkey] = value
        return True

    def newPkeyValue(self, record=None):
        """Override to generate keys; the default follows ``pkeyValue``."""
        return self.pkeyValue(record=record)

    def pkeyValue(self, record=None):
        """GenroPy pkeyValue: the default strategies, in their order."""
        model = self.model
        keys = self.pkeys
        if len(keys) > 1:
            return json.dumps([record[name] for name in keys], default=str)
        column = model.columns[model.pkey]
        attributes = column.attributes
        if column.dtype in _INTEGER_DTYPES:
            rows = self.query(columns=f'max(${model.pkey}) AS last').fetch()
            return (rows[0]['last'] or 0) + 1
        if not record:
            return get_uuid()
        pkey_columns = model.attributes.get('pkey_columns')
        if pkey_columns:
            joiner = model.attributes.get('pkey_columns_joiner') or '_'
            return joiner.join(str(record.get(name)) for name in split_names(pkey_columns)
                               if record.get(name) is not None)
        syscode = record.get('__syscode')
        if syscode:
            size = attributes.get('size')
            return syscode.ljust(int(size), '_') if size and ':' not in size else syscode
        if column.dtype in _UUID_DTYPES and attributes.get('size') in ('22', ':22', None):
            return get_uuid()
        return None

    # ------------------------------------------------------------------
    #  Field triggers
    # ------------------------------------------------------------------

    def _doFieldTriggers(self, triggerEvent, record, **kwargs):
        """Column triggers of ``triggerEvent``, in column declaration order."""
        for name, column in self.model.columns.items():
            trigger = column.attributes.get(triggerEvent)
            if not trigger:
                continue
            if callable(trigger):
                trigger(record, name)
                continue
            trigger_table = column.attributes.get('trigger_table')
            target = self.db.table(trigger_table) if trigger_table else self
            getattr(target, f'trigger_{trigger}')(record, fldname=name, tblname=self.fullname, **kwargs)

    # ------------------------------------------------------------------
    #  Related records
    # ------------------------------------------------------------------

    def _relations_many(self):
        """Joiners of the relations pointing to this table (mode 'M')."""
        joiners = []
        for node in self.model.relations:
            joiner = node.attr.get('joiner')
            if joiner and joiner.get('mode') == 'M':
                joiners.append(joiner)
        return joiners

    def _related_rows(self, joiner, value):
        mpkg, mtbl, mfld = joiner['many_relation'].split('.')
        related = self.db.table(f'{mpkg}.{mtbl}')
        columns = ','.join(f'${name}' for name in related.model.columns)
        rows = related.query(columns=columns, where=f'${mfld} = :pid', pid=value, for_update=True,
                             excludeDraft=False, excludeLogicalDeleted=False,
                             ignorePartition=True).fetch()
        return related, mfld, [dict(row) for row in rows]

    def deleteRelated(self, record):
        """Apply ``onDelete`` of the relations pointing to this table."""
        for joiner in self._relations_many():
            action, _, message = (joiner.get('onDelete') or 'ignore').partition(':')
            action = action.lower()
            if action == 'ignore':
                continue
            ofld = joiner['one_relation'].split('.')[2]
            related, mfld, rows = self._related_rows(joiner, record[ofld])
            if not rows:
                continue
            if action == 'raise':
                raise self.exception('delete', record=record,
                                     msg=message or 'Record referenced in table %(reltable)s',
                                     reltable=related.fullname)
            if action == 'cascade':
                for row in rows:
                    related.delete(row)
            elif action == 'setnull':
                for row in rows:
                    old = dict(row)
                    row[mfld] = None
                    related.update(row, old)

    def updateRelated(self, record, old_record=None):
        """Apply ``onUpdate`` of the relations whose referenced key changed."""
        for joiner in self._relations_many():
            action = (joiner.get('onUpdate') or '').lower()
            if not action or action == 'ignore':
                continue
            if old_record is None:
                raise ValueError(f'{self.fullname}: onUpdate of {joiner["many_relation"]} requires old_record')
            ofld = joiner['one_relation'].split('.')[2]
            if record.get(ofld) == old_record.get(ofld):
                continue
            related, mfld, rows = self._related_rows(joiner, old_record[ofld])
            if not rows:
                continue
            if action == 'raise':
                raise self.exception('save', record=record, msg='Record referenced in table %(reltable)s',
                                     reltable=related.fullname)
            if action == 'cascade':
                for row in rows:
                    old = dict(row)
                    row[mfld] = record[ofld]
                    related.update(row, old_record=old)
