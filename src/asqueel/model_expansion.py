"""Expand the agreed options on an owned source, following gnrdbo.sysFields.

Only structural declarations are produced. Hook names, formulas and policies
remain data; no record method, counter, query or external service runs here.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import inspect

from .catalog import SqlModelCatalog
from .common import split_names
from .contracts import UnsupportedFeatureError
from .model_source import options


def _legacy(**attributes):
    # Use the same flat namespace as the offline legacy adapter.
    return {f'x_legacy_{key}': value for key, value in attributes.items()}


class _TableExpansion:
    def __init__(self, builder, key, table):
        self.builder, self.key, self.table = builder, '.'.join(key), table

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
        return (self.spec('sys_fields') or {}).get('group') or '_'

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
        if kind == 'formulaColumn':
            data['x_requires_compilation'] = 'formulaColumn'
        return getattr(self.table, kind)(name, **data)

    def formula(self, name, formula=None, **attributes):
        return self.add(name, attributes.pop('dtype', 'A'), kind='formulaColumn',
                        sql_formula=formula, **attributes)

    def table_default(self, **attributes):
        for key, value in attributes.items():
            self.table.attr.setdefault(key, value)

    def relation(self, column, to, **attributes):
        existing = [n for n in column.value or () if n.node_tag == 'relation']
        if existing:
            if len(existing) != 1:
                raise ValueError(f'{self.key}.{column.label}: multiple relations')
            relation = existing[0]
            target = relation.get_attr('to')
            if target != to and self.key.split('.')[0] + '.' + target != to:
                raise ValueError(f'{self.key}.{column.label}: conflicting generated relation')
            defaults = (relation.attr.get('_meta') or {}).get('signature_defaults', ())
            for key, value in attributes.items():
                if key in relation.attr and key not in defaults and relation.attr[key] != value:
                    raise ValueError(f'{self.key}.{column.label}: conflicting relation {key}')
            relation.attr.update(attributes)
            return
        column.relation(to, foreign_key=True, **attributes)

    def sys_fields(self):
        spec = self.spec('sys_fields')
        if spec is None:
            return
        group = spec['group'] or '_'
        if spec['group'] and spec['group_name']:
            self.table_default(**{f'group_{group}': spec['group_name']})
        definitions = {
            'id': ('id', 'A', 'Id', {'size': '22', 'read_only': True,
                'x_generation': {'type': 'uuid', 'algorithm': 'legacy22'}, **_legacy(_sendback=True)}),
            'ins': ('__ins_ts', 'DHZ', 'Insert date', {'indexed': True, **_legacy(onInserting='setTSNow')}),
            'ldel': ('__del_ts', 'DHZ', 'Logical delete date', {'indexed': True}),
            'upd': ('__mod_ts', 'DHZ', 'Update date', {'indexed': True,
                **_legacy(onInserting='setTSNow', onUpdating='setTSNow')}),
            'user_ins': ('__ins_user', 'T', 'User Insert', _legacy(onInserting='setCurrentUser')),
            'user_upd': ('__mod_user', 'T', 'User Modify', _legacy(onInserting='setCurrentUser', onUpdating='setCurrentUser')),
            'draft': ('__is_draft', 'B', 'Is Draft', {'indexed': True, **_legacy(_sendback=True)}),
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
            self.add(name, dtype, required=required, reason='sys_fields',
                     **{'group': group, 'name_long': '!![en]' + label,
                        **_legacy(_sysfield=True), **attrs, **custom})
        if spec['id'] is not False:
            self.table_default(pkey='id')
        for flag, key, value in (
                ('ldel', 'logicalDeletionField', '__del_ts'), ('upd', 'lastTS', '__mod_ts'),
                ('draft', 'draftField', '__is_draft')):
            if spec[flag] is not False:
                self.table_default(**_legacy(**{key: value}))
        pkey = self.table.get_attr('pkey')
        if pkey:
            self.formula('__record_pointer', f" '{self.key}.' || ${pkey} ", group=group,
                         name_long='!![en]Record pointer', **_legacy(_sysfield=True))
        self.base_virtuals()

    def base_virtuals(self):
        for name, expression, label in (
            ('__protecting_reasons', True, 'Protecting reasons'),
            ('__is_protected_row', "$__protecting_reasons!=''", 'Row Protected'),
            ('__invalid_reasons', True, 'Invalid reasons'),
            ('__is_invalid_row', "$__invalid_reasons!=''", 'Invalid row'),
        ):
            self.formula(name, expression, group=self.group, name_long='!![en]' + label,
                         **_legacy(_sysfield=True))

    def local(self):
        # DbModelSrc._subtable_table exposes each declared filter as a boolean
        # virtual column. Keep the SQL and its bindings as model data.
        for child in list(self.table.value or ()):
            if child.node_tag != 'subtable':
                continue
            name = child.get_attr('name')
            bindings = {f'var_{key}': value for key, value in
                        (child.get_attr('parameters') or {}).items()}
            bindings.update({f'var_{key[10:]}': value for key, value in child.attr.items()
                             if key.startswith('condition_')})
            self.formula('subtable_' + name, child.get_attr('condition'), dtype='B',
                         name_long=child.get_attr('name_long') or name, group='subtables',
                         **_legacy(_addClass='subtable_' + name), **bindings)
            self.table_default(group_subtables='!![en]Subtables')
        spec = self.spec('full_update')
        if spec is not None:
            self.add(spec['field'], 'DHZ', indexed=True, group=self.group,
                     name_long='!![en]Full Update TS', **_legacy(_sysfield=True))
        spec = self.spec('record_hash')
        if spec is not None:
            self.add(spec['field'], group=self.group, name_long='!![en]Update date',
                     **_legacy(_sysfield=True, onInserting='setRecordMd5', onUpdating='setRecordMd5'))
        spec = self.spec('audit')
        if spec is not None:
            self.table_default(**_legacy(audit=spec['mode']))
            self.add(spec['version_field'], 'L', group=self.group, name_long='Audit version',
                     **_legacy(_sysfield=True, onInserting='setAuditVersionIns', onUpdating='setAuditVersionUpd'))
        spec = self.spec('dynamic_fields')
        if spec is not None:
            self.add('df_fields', 'X', group='_', **_legacy(_sendback=True))
            self.add('df_fbcolumns', 'L', group='_')
            self.add('df_custom_templates', 'X', group='_', **_legacy(templates=spec.get('templates')))
            self.add('df_colswidth', group='_')
        spec = self.spec('auto_counter')
        if spec is not None:
            scope = spec.get('scope')
            self.table_default(**_legacy(counter=scope or True))
            counter_attrs = _legacy(counter=True, _sysfield=True)
            if self.spec('hierarchical') is None:
                counter_attrs.update(_legacy(_counter_fkey=scope or True, onInserting='setRowCounter'))
            self.add(spec['field'], 'L', group=self.group, name_long='!![en]Counter',
                     **counter_attrs)
            if self.spec('hierarchical') is None:
                self.table_default(order_by='$' + spec['field'])
        spec = self.spec('protection')
        if spec is not None:
            # rules are only preserved; no invented rule-to-column expansion.
            if spec.get('tag'):
                self.add('__protection_tag', group=self.group, name_long='!![en]Protection tag',
                         **_legacy(_sysfield=True, _sendback=True, onInserting='setProtectionTag'))
                self.formula('__protected_by_tag', """ ( CASE WHEN $__protection_tag IS NULL THEN NULL
                                                    ELSE NOT (',' || :env_userTags || ',' LIKE '%%,'|| $__protection_tag || ',%%')
                                                    END ) """, dtype='B', **_legacy(_sysfield=True))
        # Column-level dynamic_fields is declaration data, not a new physical field.
        for column in self.table.value.get_item('columns') or ():
            child = column.value.get_node('dynamic_fields') if column.value else None
            if child is not None and child.get_attr('enabled', True):
                column.attr.update(_legacy(subfields=child.get_attr('source')))

    def hierarchy(self):
        spec = self.spec('hierarchical')
        if spec is None:
            return
        id_column = self.node('id')
        if id_column is None or self.table.get_attr('pkey') != 'id' or id_column.get_attr('size') != '22':
            raise ValueError(f'{self.key}: hierarchical requires id size 22 as primary key, as in legacy')
        parent = spec['parent']
        col = self.add(parent, 'A', required={'size': '22'}, group='*', name_long='!![en]Parent id',
                       **_legacy(_sysfield=True, onInserting='hierarchical_before',
                                 onUpdating='hierarchical_before', onUpdated='hierarchical_after'))
        self.relation(col, self.key + '.id', inverse='_children', deferred=True, on_delete='cascade',
                      one_name='!![en]Parent', many_name='!![en]Children', one_group=self.group, many_group=self.group)
        self.formula('child_count', dtype='L', group='*',
                     select=dict(table=self.key, where=f'@_children.{parent}=#THIS.id', columns='COUNT(*)'))
        self.formula('hlevel', "length($hierarchical_pkey)-length(replace($hierarchical_pkey,'/',''))+1", group='*')
        if spec['root_id']:
            col = self.add('root_id', 'A', required={'size': '22'}, group='*',
                           sql_value='substring(:hierarchical_pkey from 1 for 22)', **_legacy(_sysfield=True))
            self.relation(col, self.key + '.id', inverse='_grandchildren', deferred=True,
                          on_delete='ignore', one_name='!![en]Root', many_name='!![en]Grandchildren')
        if spec['virtual_roots']:
            self.add('_virtual_node', 'B', name_long='!![en]H.Virtual node', **_legacy(copyFromParent=True))
        columns = spec.get('columns') or ()
        columns = split_names(columns) if isinstance(columns, str) else columns
        fields = []
        counter = self.spec('auto_counter')
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
                     name_long='!![en]Parent Hierarchical ' + label, **_legacy(_sysfield=True))
            fields.append(name)
        self.add('hierarchical_pkey', required={'unique': True}, group=self.group,
                 name_long='!![en]Hierarchical pkey', **_legacy(_sysfield=True))
        self.add('_parent_h_pkey', group=self.group, **_legacy(_sysfield=True))
        fields.append('pkey')
        self.table_default(**_legacy(hierarchical=','.join(fields)))
        if spec.get('caption_field'):
            self.table_default(caption_field=spec['caption_field'])
        if spec.get('depth'):
            for name in fields:
                column = self.node('hierarchical_' + name)
                column.attr.update(_legacy(variant='hdepth', variant_hdepth_levels=spec['depth']))
                if not column.get_attr('group'):
                    column.attr['group'] = 'hierarchical_' + name
                    self.table_default(**{'group_hierarchical_' + name: column.get_attr('name_long')})
        broadcast = self.spec('broadcast')
        broadcast_fields = split_names((broadcast or {}).get('columns') or '')
        if parent not in broadcast_fields:
            broadcast_fields.append(parent)
        self.table_default(**_legacy(broadcast=','.join(broadcast_fields)))
        if counter:
            if counter.get('scope'):
                raise ValueError(f'{self.key}: hierarchical auto_counter cannot have a relative scope')
            for name in ('_h_count', '_parent_h_count'):
                self.add(name, group=self.group, **_legacy(_sysfield=True))
            formula = '$_h_count' if fields == ['pkey'] else f' COALESCE($_h_count,${fields[0]}) '
            self.formula('_h_sortcol', formula, group=self.group, **_legacy(_sysfield=True))
            self.table_default(order_by='$_h_sortcol')
        else:
            self.table_default(order_by='$hierarchical_' + fields[0])


def _target(expansions, reference, owner):
    key = reference if '.' in reference else owner.key.split('.')[0] + '.' + reference
    if key not in expansions:
        raise ValueError(f'{owner.key}: unknown related table {key!r}')
    return expansions[key]


def _attachments(owner, spec, expansions):
    master = _target(expansions, spec['master'], owner)
    pkey = master.table.get_attr('pkey')
    if not pkey or master.node(pkey) is None:
        raise ValueError(f'{owner.key}: attachment master needs a physical primary key')
    master.table_default(atc_attachmenttable=owner.key)
    label = master.table.get_attr('name_long')
    owner.table_default(caption_field='description', rowcaption='$description',
                        name_long=f'{label}  Attachment', name_plural=f'{label} Attachments')
    owner.add('id', 'A', required={'size': '22'}, group='_', name_long='Id')
    # Explicit local source labels/group win over the attachment base declaration.
    if owner.node('id').get_attr('name_long') == '!![en]Id':
        owner.node('id').attr.update(name_long='Id', group='_')
    for name, label in (('filepath', '!![en]Filepath'), ('filepath_hash', 'MD5 hash'),
                        ('filepath_original_name', '!![en]Original name'), ('external_url', '!![en]External url'),
                        ('description', '!![en]Description'), ('mimetype', '!![en]Mimetype'), ('text_content', '!![en]Content')):
        extra = _legacy(onDeleted='onDeletedAtc', onInserted='onInsertedAtc', onInserting='checkExternalUrl') if name == 'filepath' else {}
        owner.add(name, name_long=label, **extra)
    owner.add('info', 'X', name_long='!![en]Additional info')
    owner.add('is_foreign_document', 'B', name_long='!![en][Is foreign document]', name_short='!![en]Ext')
    column = owner.add('maintable_id', 'A', required={'size': '22'}, group='*', name_long=master.table.get_attr('name'))
    owner.relation(column, master.key + '.' + pkey, inverse='atc_attachments',
                   on_delete='cascade', on_delete_sql='cascade', on_duplicate=False, deferred=True)
    owner.formula('adapted_url', """CASE WHEN position('\\:' in $filepath)>0 THEN '/'||$filepath
             ELSE '/_vol/' || $filepath
            END""", group='_')
    owner.add('fileurl', 'T', kind='pyColumn', method='filepath_endpoint_url', name_long='Fileurl',
              required_columns='$external_url,$filepath', static=True)
    owner.add('missing_file', 'B', kind='pyColumn', method='pyColumn_missing_file', name_long='Missing file')
    owner.add('full_external_url', 'T', kind='pyColumn', method='pyColumn_full_external_url', name_long='Full external url')


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
                    name_long=master.table.get_attr('name_long'), **_legacy(copyFromParent=True, fkeyToMaster=True))
    owner.relation(col, master.key + '.' + pkey, inverse=owner.table.get_attr('name') + 's',
                   on_duplicate=False, deferred=True, on_delete='cascade')
    root = master.add('root_' + owner.table.get_attr('name') + '_id', 'A', required={'size': '22'},
                      name_long=f"{owner.table.get_attr('name_long')} root",
                      **_legacy(onInserting='insertLinkedHierarchicalRoot', onUpdating='updateLinkedHierarchicalRoot'))
    master.relation(root, owner.key + '.id', one_one=True, on_duplicate=False, on_delete_sql='set_null',
                    deferred=True, **_legacy(one_one='*'))
    owner.table_default(hierarchical_linked_to=master.key)


def _relative_index(owner, spec, expansions):
    name = spec['relation'].lstrip('@')
    col = owner.node(name)
    relations = [node for node in col.value or () if node.node_tag == 'relation'] if col is not None else []
    if len(relations) != 1:
        raise ValueError(f'{owner.key}: relative_index needs a column with one direct relation: {name}')
    parts = relations[0].get_attr('to').split('.')
    if len(parts) == 2:
        parts.insert(0, owner.key.split('.')[0])
    master = _target(expansions, '.'.join(parts[:2]), owner)
    xtd = _target(expansions, master.key + '_xtd', owner)
    owner.add(spec['field'], 'L', name_long='!![en]Rel.Idx', group=owner.group,
              **_legacy(onInserting='setRelidx', relidx=True, _relidx_fkey=name, _sysfield=True, format='0000'))
    owner.table_default(**_legacy(relidx=name))
    xtd.add(owner.key.replace('.', '_') + '_relidx', 'L',
            name_long=f"{owner.table.get_attr('name_long')} relidx count")


def expand_options(builder):
    catalog = SqlModelCatalog(builder)
    for path, node in catalog.nodes:
        if node.node_tag in ('system_records', 'release') and node.get_attr('enabled', True):
            raise UnsupportedFeatureError(f'{path}: {node.node_tag} is deferred; no expansion in this release')
    expansions = {'.'.join(key): _TableExpansion(builder, key, entry['node'])
                  for key, entry in catalog.tables.items()}
    with builder.contribution('@options'):
        # Compose the existing base options for AttachmentTable, on the owned source only.
        for owner in expansions.values():
            if owner.spec('attachments') is not None:
                configured = options(owner.table)
                if 'sys_fields' not in configured:
                    added = owner.table.options().sys_fields()
                    added.attr.update(owner.spec('sys_fields'))
                if 'auto_counter' not in configured:
                    added = owner.table.options().auto_counter('maintable_id')
                    added.attr.update(owner.spec('auto_counter'))
        # All local structures exist before cross-table contributions and relations.
        for owner in expansions.values():
            owner.sys_fields()
            owner.local()
        for owner in expansions.values():
            owner.hierarchy()
        for owner in expansions.values():
            spec = owner.spec('attachments')
            if spec is not None:
                _attachments(owner, spec, expansions)
        for owner in expansions.values():
            spec = owner.spec('hierarchical')
            if spec and spec.get('linked_to'):
                _linked_hierarchy(owner, spec, expansions)
        for owner in expansions.values():
            spec = owner.spec('relative_index')
            if spec is not None:
                _relative_index(owner, spec, expansions)
