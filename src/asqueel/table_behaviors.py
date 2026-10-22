"""Standalone option behaviors within the ordinary write transaction."""
from copy import deepcopy

from .common import split_names, sql_attribute_declared
from .write_compiler import toTypedJSON


class TableBehaviors:
    def _behavior(self, name):
        option = self.model.options.get(name)
        return option.attributes if option and option.attributes.get('enabled', True) else None

    def _record_key(self, record):
        if self.model.pkey in record:
            return record[self.model.pkey]
        keys = self.pkeys
        return toTypedJSON([record[name] for name in keys]) if len(keys) > 1 else record[keys[0]]

    def _behavior_rows(self, columns=None, where=None, sqlparams=None):
        columns = columns or ','.join('$' + name for name in self.model.columns)
        return self.query(columns=columns, where=where, sqlparams=sqlparams,
                          excludeDraft=False, excludeLogicalDeleted=False,
                          ignorePartition=True, addPkeyColumn=False, order_by='').fetch()

    def _related_target(self, field):
        relation = next(child for child in self.model.columns[field].values() if child.tag == 'relation')
        return self.db.table('.'.join(relation.attributes['to'].split('.')[:2]))

    def _lock_behaviors(self):
        tables = {}
        if self._behavior('hierarchical') is not None or self._behavior('auto_counter') is not None:
            tables[self.fullname] = self
        relative = self._behavior('relative_index')
        if relative is not None:
            master = self._related_target(relative['relation'].lstrip('@'))
            extension = self.db.table(master.fullname + '_xtd')
            tables[extension.fullname] = extension
        for name, column in self.model.columns.items():
            if column.attributes.get('onInserting') == 'insertLinkedHierarchicalRoot':
                target = self._related_target(name)
                tables[target.fullname] = target
        for name in sorted(tables):
            tables[name].lock('SHARE ROW EXCLUSIVE')

    def _insert_defaults(self, record):
        for name, column in self.model.columns.items():
            if name not in record and column.attributes.get('default') is not None:
                record[name] = deepcopy(column.attributes['default'])

    def _check_column_changes(self, record, old_record=None):
        for name, column in self.model.columns.items():
            if name not in record:
                continue
            attrs = column.attributes
            if old_record is None:
                if attrs.get('readOnly') and not (name == self.model.pkey and self._behavior('sys_fields') is not None
                                                 and attrs.get('x_generation') == {'type': 'uuid', 'algorithm': 'legacy22'}):
                    raise ValueError(f'{self.fullname}.{name} is read-only')
            elif attrs.get('readOnly') or attrs.get('unmodifiable') or sql_attribute_declared(attrs, 'generatedExpression'):
                value, previous = record[name], old_record.get(name)
                if column.dtype == 'A' and isinstance(value, str) and isinstance(previous, str):
                    value, previous = value.rstrip(), previous.rstrip()
                if value != previous:
                    raise ValueError(f'{self.fullname}.{name} is unmodifiable')

    def _sql_record(self, record):
        return {name: value for name, value in record.items()
                if name not in self.model.columns
                or not sql_attribute_declared(self.model.columns[name].attributes, 'generatedExpression')}

    def _next_counter(self, field, scope, record):
        predicates, params = [], {}
        for index, name in enumerate(split_names(scope)):
            if name not in self.model.columns:
                raise ValueError(f'{self.fullname}: counter scope must be a physical column: {name}')
            value = record.get(name)
            if value is None:
                predicates.append(f'${name} IS NULL')
            else:
                params[f'scope_{index}'] = value
                predicates.append(f'${name} = :scope_{index}')
        rows = self._behavior_rows(f'MAX(${field}) AS counter_max', ' AND '.join(predicates) or None, params)
        return (rows[0]['counter_max'] or 0) + 1

    def trigger_setRowCounter(self, record, fldname, **kwargs):
        if record.get(fldname) is None:
            record[fldname] = self._next_counter(fldname, self._behavior('auto_counter').get('scope'), record)

    def trigger_setRelidx(self, record, fldname, **kwargs):
        if record.get(fldname) is not None:
            return
        name = self._behavior('relative_index')['relation'].lstrip('@')
        extension = self.db.table(self._related_target(name).fullname + '_xtd')
        master = record.get(name)
        if master is None:
            raise ValueError('A relative index requires a master key')
        counter = self.fullname.replace('.', '_') + '_relidx'
        rows = extension._behavior_rows(where='$main_id=:master', sqlparams={'master': master})
        if len(rows) > 1:
            raise ValueError('A relative index requires one extension record per master')
        if rows:
            old = dict(rows[0])
            value = (old.get(counter) or 0) + 1
            extension.update(dict(old, **{counter: value}), old_record=old, ignore_partition=True)
        else:
            value = 1
            if extension.model.pkey not in ('id', 'main_id'):
                raise ValueError('Relative-index extension requires id or main_id as its primary key')
            extension.insert({'main_id': master, extension.model.pkey: master, counter: value}, ignore_partition=True)
        record[fldname] = value

    def _finish_behaviors(self, record, prepared, old_record=None):
        spec = self._behavior('hierarchical')
        if spec is not None and record != prepared:
            parent = spec.get('parent', 'parent_id')
            moved = record.get(parent) != prepared.get(parent)
            if moved and old_record is None and self._behavior('auto_counter') is not None:
                record[self._behavior('auto_counter').get('field', '_row_count')] = None
            self.hierarchicalHandler.trigger_before(record, old_record=old_record, allocate=moved)
        for name, column in self.model.columns.items():
            if column.attributes.get('onUpdating') == 'updateLinkedHierarchicalRoot':
                self.trigger_updateLinkedHierarchicalRoot(record, name, old_record=dict(old_record or {}, **prepared))

    def trigger_insertLinkedHierarchicalRoot(self, record, fldname, **kwargs):
        target = self._related_target(fldname)
        key = record.get(self.model.pkey)
        if key is None:
            record.pop(fldname, None)
            return  # The INSERT must return the database-generated master key first.
        values = {f'{self.model.name}_{self.model.pkey}': key,
                  'id': str(key).rstrip().ljust(22, '_')}
        values.update({name: record[name] for name in target.model.attributes['x_legacy_hierarchical'].split(',')
                       if name != 'pkey' and name in record})
        target.insert(values)
        record[fldname] = values['id']

    def _complete_linked_insert(self, record, before_sql, *, ignore_partition=False):
        for name, column in self.model.columns.items():
            if column.attributes.get('onInserting') != 'insertLinkedHierarchicalRoot':
                continue
            if record.get(name) is not None:
                self.trigger_updateLinkedHierarchicalRoot(record, name, old_record=before_sql)
                continue
            self.trigger_insertLinkedHierarchicalRoot(record, name)
            if record.get(name) is None:
                raise ValueError('The database did not return the linked hierarchy master key')
            self.sql_update({self.model.pkey: record[self.model.pkey], name: record[name]},
                            ignore_partition=ignore_partition)

    def trigger_updateLinkedHierarchicalRoot(self, record, fldname, old_record=None, **kwargs):
        target = self._related_target(fldname)
        if fldname in record and record[fldname] != old_record.get(fldname):
            raise ValueError('Linked hierarchy roots are unmodifiable')
        values = {name: record[name] for name in target.model.attributes['x_legacy_hierarchical'].split(',')
                  if name != 'pkey' and name in record and record[name] != old_record.get(name)}
        root = record.get(fldname, old_record.get(fldname))
        if values and root is not None:
            old = target._reread(root)
            target.update(dict(old, **values), old_record=old)
