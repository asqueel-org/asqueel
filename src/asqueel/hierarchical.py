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

    def trigger_before(self, record, old_record=None):
        tblobj = self.tblobj
        pkeyfield = tblobj.model.pkey
        # asqueel updates accept a partial record: an absent key keeps its stored value.
        current = dict(old_record or {}, **record)
        parent_id = current.get('parent_id')
        moved = old_record is not None and _changed(('parent_id',), current, old_record)
        has_counter = '_row_count' in tblobj.model.columns
        # doc 36 §10.2: a moved node takes the last position among its new siblings.
        next_position = has_counter and (moved or (old_record is None and record.get('_row_count') is None))
        parent_record = None
        if parent_id:
            # Locking the parent serializes max + 1 among its children.
            rows = tblobj.query(where=f'${pkeyfield}=:pid', pid=parent_id, for_update=next_position,
                                excludeLogicalDeleted=False, excludeDraft=False).fetch()
            parent_record = rows[0] if rows else None
        elif next_position:
            self.lock_roots()
        if parent_record and moved and record[pkeyfield] in parent_record['hierarchical_pkey'].split('/'):
            raise tblobj.exception('business_logic', msg='A node cannot be moved under itself or one of its descendants')
        if next_position:
            # Assigned before the paths: '_row_count' can be a hierarchical field.
            where, params = ('$parent_id =:p_id', {'p_id': parent_id}) if parent_id else ('$parent_id IS NULL', {})
            rows = tblobj.query(columns='$_row_count', where=where, sqlparams=params,
                                order_by='$_row_count desc', limit=1,
                                excludeLogicalDeleted=False, excludeDraft=False).fetch()
            record['_row_count'] = current['_row_count'] = ((rows[0]['_row_count'] if rows else None) or 0) + 1
        # doc 36 §10.2: the bound applies to a position being written, not to a stored one.
        positioned = old_record is None or _changed(('_row_count',), current, old_record)
        if has_counter and positioned and (current.get('_row_count') or 0) > _MAX_SIBLINGS:
            raise tblobj.exception('business_logic', msg=f'at most {_MAX_SIBLINGS} siblings under one parent')
        for fld in tblobj.model.attributes['x_legacy_hierarchical'].split(','):
            parent_h_fld = '_parent_h_%s' % fld
            h_fld = 'hierarchical_%s' % fld
            v = current.get(pkeyfield if fld == 'pkey' else fld)
            record[parent_h_fld] = parent_record[h_fld] if parent_record else None
            record[h_fld] = '%s/%s' % (parent_record[h_fld], v) if parent_record else v
        if parent_record:
            for field, colobj in tblobj.model.columns.items():
                if colobj.attributes.get('x_legacy_copyFromParent'):
                    record[field] = parent_record[field]
        if not has_counter:
            return
        record['_parent_h_count'] = current['_parent_h_count'] = parent_record['_h_count'] if parent_record else None
        if old_record is None or _changed(('_row_count', '_parent_h_count'), current, old_record):
            record['_h_count'] = '%s%s' % (record['_parent_h_count'] or '', encode36(current['_row_count'], 2))

    def lock_roots(self):
        """Serialize max + 1 among the roots; SQLite writes are already serialized."""
        db = self.tblobj.db
        compiled = db.write_compiler.lock_table(self.tblobj.model, db.environment.snapshot(), mode='SHARE ROW EXCLUSIVE')
        if compiled is not None:
            db.execute(compiled).close()

    def trigger_after(self, record, old_record=None):
        tblobj = self.tblobj
        if old_record is None:
            raise tblobj.exception('standard', msg='Updating a hierarchical record requires old_record')
        current = dict(old_record, **record)
        hfields = tblobj.model.attributes['x_legacy_hierarchical'].split(',')
        changed_hfields = [fld for fld in hfields
                           if record.get('hierarchical_%s' % fld) != old_record.get('hierarchical_%s' % fld)]
        order_by = None
        changed_counter = False
        if '_row_count' in current:
            order_by = '$_row_count'
            changed_counter = _changed(('_row_count', '_parent_h_count'), current, old_record)
        if not (changed_hfields or changed_counter):
            return
        columns = ','.join(f'${name}' for name in tblobj.model.columns)
        fetch = tblobj.query(columns=columns, where='$parent_id=:curr_id', addPkeyColumn=False, for_update=True,
                             curr_id=record[tblobj.model.pkey], order_by=order_by, bagFields=True,
                             excludeLogicalDeleted=False, excludeDraft=False).fetch()
        for k, row in enumerate(fetch):
            row = dict(row)
            new_row = dict(row)
            for fld in changed_hfields:
                new_row['_parent_h_%s' % fld] = record['hierarchical_%s' % fld]
            if changed_counter:
                if new_row.get('_row_count') is None:
                    new_row['_row_count'] = k + 1
                new_row['_parent_h_count'] = current['_h_count']
                new_row['_h_count'] = '%s%s' % (new_row['_parent_h_count'] or '', encode36(new_row['_row_count'], 2))
            tblobj.update(new_row, row)
