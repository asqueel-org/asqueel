"""Hierarchical tables, as GenroPy HierarchicalHandler (develop 95da66ee64).

Reference gnr/sql/gnrsqltable_proxy/hierarchical.py trigger_before and
trigger_after. The legacy ``subtable='*'`` has no asqueel counterpart and is
dropped.
"""
from __future__ import annotations

_BASE36 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
# Two base-36 digits of _h_count per level.
_MAX_SIBLINGS = 36 ** 2 - 1


def encode36(number, nChars=1):
    """Legacy gnr/core/gnrstring.py encode36: '' when ``number`` needs more than ``nChars``."""
    result = []
    while number >= 1:
        result.insert(0, _BASE36[number % 36])
        number //= 36
    if len(result) > nChars:
        return ''
    return ''.join(result).rjust(nChars, _BASE36[0])


def _changed(fields, record, old_record):
    return any(record.get(name) != old_record.get(name) for name in fields)


class HierarchicalHandler:
    """Paths, counters and subtree rewrites of a table declared hierarchical."""

    def __init__(self, tblobj):
        self.tblobj = tblobj

    def trigger_before(self, record, old_record=None, *, allocate=True):
        tblobj = self.tblobj
        pkeyfield = tblobj.model.pkey
        # asqueel updates accept a partial record: an absent key keeps its stored value.
        current = dict(old_record or {}, **record)
        spec = tblobj._behavior('hierarchical')
        parent_field = spec.get('parent', 'parent_id')
        counter_field = (tblobj._behavior('auto_counter') or {}).get('field', '_row_count')
        key = str(current[pkeyfield]).rstrip()
        if '/' in key:
            raise ValueError('Hierarchical primary keys cannot contain /')
        if old_record and key != str(old_record[pkeyfield]).rstrip():
            raise ValueError('Hierarchical primary keys are unmodifiable')
        parent_id = current.get(parent_field)
        if parent_id is not None and str(parent_id).rstrip() == key:
            raise tblobj.exception('business_logic', msg='A node cannot be moved under itself or one of its descendants')
        moved = old_record is not None and _changed((parent_field,), current, old_record)
        has_counter = counter_field in tblobj.model.columns
        # doc 36 §10.2: a moved node takes the last position among its new siblings.
        next_position = allocate and has_counter and (moved or (old_record is None and record.get(counter_field) is None))
        parent_record = None
        if parent_id:
            # Locking the parent serializes max + 1 among its children.
            rows = tblobj.query(where=f'${pkeyfield}=:pid', pid=parent_id, for_update=next_position,
                                excludeLogicalDeleted=False, excludeDraft=False, ignorePartition=True).fetch()
            parent_record = rows[0] if rows else None
        elif next_position:
            self.lock_roots()
        if parent_id is not None and parent_record is None:
            raise ValueError('Unknown hierarchical parent')
        if parent_record and key in parent_record['hierarchical_pkey'].split('/'):
            raise tblobj.exception('business_logic', msg='A node cannot be moved under itself or one of its descendants')
        if next_position:
            # Assigned before the paths: '_row_count' can be a hierarchical field.
            record[counter_field] = current[counter_field] = tblobj._next_counter(counter_field, [parent_field], current)
        # doc 36 §10.2: the bound applies to a position being written, not to a stored one.
        positioned = old_record is None or _changed((counter_field,), current, old_record)
        if has_counter and positioned and (current.get(counter_field) or 0) > _MAX_SIBLINGS:
            raise tblobj.exception('business_logic', msg=f'at most {_MAX_SIBLINGS} siblings under one parent')
        if has_counter and (type(current.get(counter_field)) is not int or current[counter_field] < 0):
            raise ValueError('Hierarchical counters require a nonnegative integer')
        for fld in tblobj.model.attributes['x_legacy_hierarchical'].split(','):
            parent_h_fld = '_parent_h_%s' % fld
            h_fld = 'hierarchical_%s' % fld
            v = key if fld == 'pkey' else current.get(fld)
            record[parent_h_fld] = parent_record[h_fld] if parent_record else None
            record[h_fld] = '%s/%s' % (parent_record[h_fld], v) if parent_record else v
        if spec.get('root_id'):
            record['root_id'] = record['hierarchical_pkey'].split('/')[0]
        if parent_record:
            for field, colobj in tblobj.model.columns.items():
                if colobj.attributes.get('x_legacy_copyFromParent'):
                    record[field] = parent_record[field]
        if not has_counter:
            return
        record['_parent_h_count'] = current['_parent_h_count'] = parent_record['_h_count'] if parent_record else None
        if old_record is None or _changed((counter_field, '_parent_h_count'), current, old_record):
            record['_h_count'] = '%s%s' % (record['_parent_h_count'] or '', encode36(current[counter_field], 2))

    def lock_roots(self):
        """Serialize max + 1 among the roots."""
        db = self.tblobj.db
        db.execute(db.write_compiler.lock_table(self.tblobj.model, db.environment_snapshot(),
                                                mode='SHARE ROW EXCLUSIVE')).close()

    def trigger_after(self, record, old_record=None):
        tblobj = self.tblobj
        if old_record is None:
            raise tblobj.exception('standard', msg='Updating a hierarchical record requires old_record')
        current = dict(old_record, **record)
        fields = [name for name, column in tblobj.model.columns.items()
                  if name.startswith('hierarchical_') or name == '_h_count'
                  or column.attributes.get('x_legacy_copyFromParent')]
        if not _changed(fields, current, old_record):
            return
        parent = tblobj._behavior('hierarchical').get('parent', 'parent_id')
        children = tblobj._behavior_rows(where=f'${parent}=:parent', sqlparams={'parent': current[tblobj.model.pkey]})
        for row in children:
            old = dict(row)
            tblobj.update(dict(old), old_record=old, ignore_partition=True)
