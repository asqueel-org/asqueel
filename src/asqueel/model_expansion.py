"""Expand the agreed options on an owned source, following gnrdbo.sysFields.

Only structural declarations are produced. Hook names, formulas and policies
remain data; no record method, counter, query or external service runs here.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import inspect

from .catalog import SqlModelCatalog
from .common import in_attribute_family, split_names
from .contracts import UnsupportedFeatureError
from .model_source import options


class _TableExpansion:
    def __init__(self, builder, key, table, *, options_first=False):
        self.builder, self.key, self.table = builder, '.'.join(key), table
        self.options_first = options_first
        self.emitted = {}

    def spec(self, name):
        option = options(self.table).get(name)
        if option is None or not option.enabled:
            return None
        info = self.builder._get_schema_info(name)
        result = {key: deepcopy(default) for key, (_, _, default) in
                  (info.get('call_args_validations') or {}).items()
                  if default is not inspect.Parameter.empty}
        result.update(option.attributes)
        return result

    @property
    def group(self):
        return (self.spec('sysFields') or {}).get('group') or '_'

    def node(self, name):
        for collection in ('columns', 'virtual_columns', 'composites'):
            found = self.table.value.get_node(f'{collection}.{name}') if self.table.value else None
            if found is not None:
                return found
        return None

    def add(self, name, dtype='T', *, kind='column', required=None, reason='option', **attributes):
        existing = self.node(name)
        structure = {'dtype': dtype, **(required or {})}
        previous = {}
        if existing is not None:
            if existing.node_tag != kind:
                raise ValueError(f'{self.key}.{name}: conflicts with {reason} element kind')
            defaults = (existing.attr.get('_meta') or {}).get('signature_defaults', ())
            previous = {k: v for k, v in existing.attr.items() if k not in ('_meta', 'name')
                        and k not in defaults}
            for key, value in structure.items():
                if previous.get(key) is not None and previous[key] != value:
                    raise ValueError(f'{self.key}.{name}: conflicts with {reason} {key}')
            if kind != 'column':
                for key in ('sql_formula', 'select', 'method'):
                    if key in previous and key in attributes and previous[key] != attributes[key]:
                        raise ValueError(f'{self.key}.{name}: conflicts with {reason} {key}')
        data = {**attributes, **previous, **structure}
        declared = self.builder._get_schema_info(kind).get('declared_names') or set()
        generated = {key: data.pop(key) for key in list(data)
                     if key not in declared and not in_attribute_family(self.builder, kind, key)}
        # The tree renderer consumes options before ordinary declarations.
        # Keep the complete source available for validation/cross-table reads,
        # but insert each generated field at the next option position.
        collection = 'columns' if kind == 'column' else 'virtual_columns'
        emitted = self.emitted.setdefault(collection, set())
        first = self.options_first and name not in emitted
        position = len(emitted) if first else None
        result = getattr(self.table, kind)(name, node_position=position, **data)
        result.attr.update(generated)
        if first:
            if existing is not None:
                # Composition updates a predeclared node in place. Preserve its
                # children and attributes while consuming it in this first pass.
                siblings = result.parent_bag
                siblings.move(siblings.keys().index(result.label), position)
            emitted.add(name)
        return result

    def formula(self, name, formula=None, **attributes):
        return self.add(name, attributes.pop('dtype', 'A'), kind='formulaColumn',
                        sql_formula=formula, **attributes)

    def table_default(self, **attributes):
        self.table.attr.update({key: value for key, value in attributes.items() if key not in self.table.attr})

    def relation(self, column, to, **attributes):
        existing = [n for n in column.value or () if n.node_tag == 'relation']
        if existing:
            if len(existing) != 1:
                raise ValueError(f'{self.key}.{column.label}: multiple relations')
            relation = existing[0]
            target = relation.get_attr('related_column')
            if target != to and self.key.split('.')[0] + '.' + target != to:
                raise ValueError(f'{self.key}.{column.label}: conflicting generated relation')
            defaults = (relation.attr.get('_meta') or {}).get('signature_defaults', ())
            for key, value in attributes.items():
                if key in relation.attr and key not in defaults and relation.attr[key] != value:
                    raise ValueError(f'{self.key}.{column.label}: conflicting relation {key}')
            relation.attr.update(attributes)
            return
        declared = self.builder._get_schema_info('relation').get('declared_names') or set()
        relation = column.relation(to, foreign_key=True,
                                   **{key: value for key, value in attributes.items() if key in declared})
        relation.attr.update({key: value for key, value in attributes.items() if key not in declared})

    def system_columns(self):
        spec = self.spec('sysFields')
        if spec is None:
            return
        group = spec['group'] or '_'
        if spec['group'] and spec['group_name']:
            self.table_default(**{f'group_{group}': spec['group_name']})
        definitions = {
            'id': ('id', 'A', 'Id', {'size': '22', 'readOnly': True}),
            'ins': ('__ins_ts', 'DHZ', 'Insert date', {'indexed': True, 'onInserting': 'setTSNow'}),
            'ldel': ('__del_ts', 'DHZ', 'Logical delete date', {'indexed': True}),
            'upd': ('__mod_ts', 'DHZ', 'Update date', {'indexed': True,
                'onInserting': 'setTSNow', 'onUpdating': 'setTSNow'}),
            'user_ins': ('__ins_user', 'T', 'User Insert', {'onInserting': 'setCurrentUser'}),
            'user_upd': ('__mod_user', 'T', 'User Modify', {'onInserting': 'setCurrentUser', 'onUpdating': 'setCurrentUser'}),
            'draft': ('__is_draft', 'B', 'Is Draft', {'indexed': True}),
            'syscode': ('__syscode', 'A', 'Internal code', {'size': ':20', 'indexed': True, 'unique': True}),
        }
        for setting, (name, dtype, label, attrs) in definitions.items():
            enabled = spec[setting]
            if enabled is False:
                continue
            custom = dict(enabled) if isinstance(enabled, Mapping) else {}
            custom.pop('type', None)
            required = {'size': '22'} if setting == 'id' else {}
            if setting == 'syscode':
                required.update(size=':20', indexed=True, unique=True)
            self.add(name, dtype, required=required, reason='sysFields',
                     **{'group': group, 'name_long': '!![en]' + label, **attrs, **custom})
        if spec['id'] is not False:
            self.table_default(pkey='id')
        for flag, key, value in (
                ('ldel', 'logicalDeletionField', '__del_ts'), ('upd', 'lastTS', '__mod_ts'),
                ('draft', 'draftField', '__is_draft')):
            if spec[flag] is not False:
                self.table_default(**{key: value})
        pkey = self.table.get_attr('pkey')
        if pkey:
            self.formula('__record_pointer', f" '{self.key}.' || ${pkey} ", group=group,
                         name_long='!![en]Record pointer')
        self.base_virtuals()

    def base_virtuals(self):
        for name, expression, label in (
            ('__protecting_reasons', True, 'Protecting reasons'),
            ('__is_protected_row', "$__protecting_reasons!=''", 'Row Protected'),
            ('__invalid_reasons', True, 'Invalid reasons'),
            ('__is_invalid_row', "$__invalid_reasons!=''", 'Invalid row'),
        ):
            self.formula(name, expression, group=self.group, name_long='!![en]' + label)

    def local(self):
        spec = self.spec('fullUpd')
        if spec is not None:
            self.add(spec['field'], 'DHZ', indexed=True, group=self.group,
                     name_long='!![en]Full Update TS')
        spec = self.spec('df')
        if spec is not None:
            self.add('df_fields', 'X', group='_')
            self.add('df_fbcolumns', 'L', group='_')
            self.add('df_custom_templates', 'X', group='_')
            self.add('df_colswidth', group='_')
        spec = self.spec('counter')
        if spec is not None:
            counter_attrs = {}
            if self.spec('hierarchical') is None:
                counter_attrs['onInserting'] = 'setRowCounter'
            self.add(spec['field'], 'L', group=self.group, name_long='!![en]Counter',
                     **counter_attrs)
            if self.spec('hierarchical') is None:
                self.table_default(order_by='$' + spec['field'])

    def hierarchy(self):
        spec = self.spec('hierarchical')
        if spec is None:
            return
        for name in ('depth',):
            if spec.get(name):
                raise UnsupportedFeatureError(f'{self.key}: hierarchical {name} is not available in this release')
        id_column = self.node('id')
        if id_column is None or self.table.get_attr('pkey') != 'id' or id_column.get_attr('size') != '22':
            raise ValueError(f'{self.key}: hierarchical requires id size 22 as primary key, as in legacy')
        parent = spec['parent']
        col = self.add(parent, 'A', required={'size': '22'}, group='*', name_long='!![en]Parent id',
                       onInserting='hierarchical_before', onUpdating='hierarchical_before',
                       onUpdated='hierarchical_after')
        self.relation(col, self.key + '.id', relation_name='_children', deferred=True, onDelete='cascade',
                      one_name='!![en]Parent', many_name='!![en]Children', one_group=self.group, many_group=self.group)
        self.formula('child_count', dtype='L', group='*',
                     select=dict(table=self.key, where=f'${parent}=#THIS.id', columns='COUNT(*)'))
        self.formula('hlevel', "length($hierarchical_pkey)-length(replace($hierarchical_pkey,'/',''))+1", group='*')
        if spec['root_id']:
            col = self.add('root_id', 'A', required={'size': '22'}, group='*',
                           sql_value='substr(:hierarchical_pkey,1,22)')
            self.relation(col, self.key + '.id', relation_name='_grandchildren', deferred=True,
                          onDelete='ignore', one_name='!![en]Root', many_name='!![en]Grandchildren')
        if spec['virtual_roots']:
            self.add('_virtual_node', 'B', name_long='!![en]H.Virtual node')
        columns = spec.get('columns') or ()
        columns = split_names(columns) if isinstance(columns, str) else columns
        fields = []
        counter = self.spec('counter')
        for item in columns:
            name = item['name'] if isinstance(item, Mapping) else item
            if name == 'pkey':
                continue
            original = self.node(name)
            if original is None:
                raise ValueError(f'{self.key}: unknown hierarchical field {name!r}')
            # In the legacy config_db recipes sysFields declares these before
            # the descriptive base columns: their default caption is the name.
            label = name
            unique = item.get('unique', False) if isinstance(item, Mapping) else False
            self.add('hierarchical_' + name, required={'unique': unique},
                     name_long='!![en]Hierarchical ' + label, hierarchical_field_of=name)
            self.add('_parent_h_' + name, group=self.group,
                     name_long='!![en]Parent Hierarchical ' + label)
            fields.append(name)
        self.add('hierarchical_pkey', required={'unique': True}, group=self.group,
                 name_long='!![en]Hierarchical pkey')
        self.add('_parent_h_pkey', group=self.group)
        fields.append('pkey')
        if spec.get('caption_field'):
            self.table_default(caption_field=spec['caption_field'])
        if counter:
            if counter.get('scope'):
                raise ValueError(f'{self.key}: hierarchical counter cannot have a relative scope')
            for name in ('_h_count', '_parent_h_count'):
                self.add(name, group=self.group)
            formula = '$_h_count' if fields == ['pkey'] else f' COALESCE($_h_count,${fields[0]}) '
            self.formula('_h_sortcol', formula, group=self.group)
            self.table_default(order_by='$_h_sortcol')
        else:
            self.table_default(order_by='$hierarchical_' + fields[0])


def _target(expansions, reference, owner):
    key = reference if '.' in reference else owner.key.split('.')[0] + '.' + reference
    if key not in expansions:
        raise ValueError(f'{owner.key}: unknown related table {key!r}')
    return expansions[key]


def _linked_hierarchy(owner, spec, expansions):
    master = _target(expansions, spec['linked_to'], owner)
    pkey = master.table.get_attr('pkey')
    column = master.node(pkey) if pkey else None
    if column is None or column.node_tag != 'column':
        raise ValueError(f'{owner.key}: linked hierarchy master needs a physical primary key')
    dtype = column.get_attr('dtype') or ('A' if column.get_attr('size') else 'T')
    dtype = {'serial': 'L', 'serial4': 'I'}.get(dtype, dtype)
    required = {'size': column.get_attr('size')} if column.get_attr('size') else {}
    name = master.table.get_attr('name')
    col = owner.add(f'{name}_{pkey}', dtype, required=required, group='_',
                    name_long=master.table.get_attr('name_long'))
    owner.relation(col, master.key + '.' + pkey, relation_name=owner.table.get_attr('name') + 's',
                   onDuplicate=False, deferred=True, onDelete='cascade')
    root = master.add('root_' + owner.table.get_attr('name') + '_id', 'A', required={'size': '22'},
                      name_long=f"{owner.table.get_attr('name_long')} root",
                      onInserting='insertLinkedHierarchicalRoot', onUpdating='updateLinkedHierarchicalRoot')
    master.relation(root, owner.key + '.id', one_one='*', onDuplicate=False, onDelete_sql='setnull',
                    deferred=True)
    owner.table_default(hierarchical_linked_to=master.key)


def _relative_index(owner, spec, expansions):
    name = spec['relation'].lstrip('@')
    col = owner.node(name)
    relations = [node for node in col.value or () if node.node_tag == 'relation'] if col is not None else []
    if len(relations) != 1:
        raise ValueError(f'{owner.key}: relidx needs a column with one direct relation: {name}')
    parts = relations[0].get_attr('related_column').split('.')
    if len(parts) == 2:
        parts.insert(0, owner.key.split('.')[0])
    master = _target(expansions, '.'.join(parts[:2]), owner)
    xtd = _target(expansions, master.key + '_xtd', owner)
    owner.add(spec['field'], 'L', name_long='!![en]Rel.Idx', group=owner.group, onInserting='setRelidx')
    xtd.add(owner.key.replace('.', '_') + '_relidx', 'L',
            name_long=f"{owner.table.get_attr('name_long')} relidx count")


def _cached_fetch_catalog(database):
    if 'cachedFetch' not in options(database):
        return
    packages = database.value.get_node('packages') if database.value is not None else None
    packages = database.packages() if packages is None else packages
    table = packages.package('_asql_', sqlschema='_asql_', sqlprefix=False).table(
        '_asql_cached_fetch', pkey='id')
    for name, dtype in (('id', 'A'), ('owner', 'A'), ('name', 'A'), ('tablename', 'A'),
                        ('sqlschema', 'A'), ('sqltable', 'A'), ('rowcount', 'L'), ('created', 'DHZ'),
                        ('user', 'A'), ('sort_sqltable', 'A'), ('sort_order_by', 'T'),
                        ('search_seed', 'T')):
        table.column(name, dtype=dtype, indexed=name == 'owner' or None)


def expand_options(builder, *, options_first=False):
    database = SqlModelCatalog(builder).database
    if database is not None:
        with builder.contribution('@options'):
            _cached_fetch_catalog(database)
    catalog = SqlModelCatalog(builder)
    for path, node in catalog.nodes:
        if node.node_tag in ('sysrecords', 'release') and node.get_attr('enabled', True):
            raise UnsupportedFeatureError(f'{path}: {node.node_tag} is deferred; no expansion in this release')
    expansions = {'.'.join(key): _TableExpansion(builder, key, entry['node'], options_first=options_first)
                  for key, entry in catalog.tables.items()}
    with builder.contribution('@options'):
        # All local structures exist before cross-table contributions and relations.
        for owner in expansions.values():
            owner.system_columns()
            owner.local()
        for owner in expansions.values():
            owner.hierarchy()
        for owner in expansions.values():
            hierarchy = owner.spec('hierarchical')
            if hierarchy and hierarchy.get('linked_to'):
                _linked_hierarchy(owner, hierarchy, expansions)
        for owner in expansions.values():
            spec = owner.spec('relidx')
            if spec is not None:
                _relative_index(owner, spec, expansions)
