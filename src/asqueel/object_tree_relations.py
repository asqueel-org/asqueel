"""Legacy global relation Bag and lazy per-table field/relation trees.

DbModel.addRelation and RelationTreeResolver._fields are the reference
algorithms. Native spelling is translated once; no SQL or JOIN is built here.
"""
from __future__ import annotations

from copy import deepcopy
import logging

from genro_bag import Bag, BagResolver

logger = logging.getLogger(__name__)


def _action(value):
    if value is None:
        return None
    name, separator, message = value.partition(':')
    name = name.lower().replace(' ', '_')
    name = {'set_null': 'setnull', 'no_action': None}.get(name, name)
    # The optional ':message' of an application action is kept as written.
    return name + separator + message if name and separator else name


def _joiner(table, column, target, attrs):
    inverse = attrs.get('relation_name')
    many = f'{table.fullname}.{column.name}'
    result = dict(
        many_relation=many, one_relation=target,
        many_rel_name=attrs.get('many_name'), one_rel_name=attrs.get('one_name') or column.attributes.get('name_long'),
        many_order_by=attrs.get('many_order_by'), one_one=attrs.get('one_one'),
        onDelete=_action(attrs.get('x_app_on_delete')),
        onDelete_sql=_action(attrs.get('on_delete')),
        onUpdate=_action(attrs.get('x_app_on_update')),
        onUpdate_sql=_action(attrs.get('on_update', 'cascade')),
        onDuplicate=attrs.get('on_duplicate'), deferred=attrs.get('deferred'),
        private_relation=not bool(inverse), case_insensitive=attrs.get('case_insensitive', False),
        one_group=attrs.get('one_group'), many_group=attrs.get('many_group'),
    )
    # These legacy attributes remain opaque data; their execution is not added.
    for key in ('eager_one', 'eager_many', 'external_relation', 'ignore_tenant',
                'storefield', 'between', 'cnd', 'join_on', 'virtual'):
        result[key] = attrs.get(key)
    return result, inverse or many.replace('.', '_')


def build_relations(model):
    """Register both directions after all table/column objects are available."""
    for table in model.tables.values():
        owners = (*table.columns.values(), *table.virtual_columns.values(), *table.composites.values())
        for column in owners:
            declarations = [child for child in column.values() if child.tag in ('relation', 'weak_relation')]
            if len(declarations) > 1:
                raise ValueError(f'Multiple relations on {table.fullname}.{column.name}')
            for declaration in declarations:
                attrs = dict(declaration.attributes)
                defaults = (declaration.structnode.attr.get('_meta') or {}).get('signature_defaults', ())
                for flag in ('one_one', 'deferred'):
                    if flag in defaults and attrs.get(flag) is False:
                        attrs.pop(flag)
                _register_relation(model, table, column, attrs)
    _inherit_alias_relations(model)


def _register_relation(model, table, column, attrs):
    """Register a declared or inherited edge through the same legacy algorithm."""
    virtual = column.tag != 'column'
    if virtual:
        attrs.update(virtual=True, one_name=attrs.get('one_name') or column.name_long)
    target = attrs['to'].split('.')
    if len(target) == 2 and target[0] not in model.namespaces:
        target.insert(0, table.pkg.name)
    if len(target) == 2:
        target.append(model.table('.'.join(target)).pkey)
    if len(target) != 3 or not target[2]:
        raise ValueError(f'Invalid relation target: {attrs["to"]!r}')
    remote = model.table('.'.join(target[:2]))
    remote_column = remote.column(target[2])
    # A virtual scalar is already a key expression. Resolving an alias here
    # would cache a partial relation tree while registration is still running.
    local_fields = ((column.name,) if virtual and column.tag != 'compositeColumn'
                    else model.physical_columns(table, column.name))
    remote_fields = model.physical_columns(remote, remote_column.name)
    if len(local_fields) != len(remote_fields):
        raise ValueError(f'Relation key length mismatch: {column.fullname}')
    for local, distant in (() if virtual else zip(local_fields, remote_fields)):
        left, right = table.column(local), remote.column(distant)
        if left.attributes.get('size') != right.attributes.get('size'):
            logger.warning('Different size in relation %s -> %s', left.fullname, right.fullname)
    target_name = '.'.join(target)
    common, inverse = _joiner(table, column, target_name, attrs)
    forward = attrs.get('name') or column.name
    entries = [
        (f'{table.fullname}.@{forward}', dict(common, mode='O',
         foreignkey=bool(attrs.get('foreign_key')), relation_name=inverse,
         resolver_kwargs=deepcopy(attrs.get('resolver_kwargs') or {}))),
        (f'{remote.fullname}.@{inverse}', dict(common, mode='M', one_rel_name=attrs.get('one_name'))),
    ]
    for path, values in entries:
        if model.relations.get_node(path) is not None:
            raise ValueError(f'Duplicate relation: {path}')
        model.relations.set_item(path, None, _attributes=values)
    if not virtual:
        # checkRelationIndex: native indexed=False remains explicit.
        for owner, fields in ((table, local_fields), (remote, remote_fields)):
            if owner.pkey and fields == model.physical_columns(owner, owner.pkey):
                continue
            if len(fields) == 1 and owner.column(fields[0]).attributes.get('indexed') is False:
                continue
            if owner is table and attrs.get('indexed') is False:
                continue
            owner._column_index(','.join(fields))


def _inherit_alias_relations(model):
    """Inherit an alias target's forward edge after all explicit edges exist.

    Only the target is inherited. FK constraints, inverse names/cardinality and
    lifecycle actions belong to the original owner, not to this derived key.
    Work on the registry, without resolving/caching incomplete relation trees.
    """
    aliases = {column.fullname: column for table in model.tables.values()
               for column in table.virtual_columns.values() if column.tag == 'aliasColumn'}
    forward = {node.attr['many_relation']: node.attr
               for package in model.relations for table in package.value
               for node in table.value if node.attr['mode'] == 'O'}
    active, done = set(), set()

    def target_column(table, path):
        parts = path.removeprefix('$').split('.')
        for part in parts[:-1]:
            node = model.relations.get_node(f'{table.fullname}.{part}')
            if node is None:
                alias = aliases.get(f'{table.fullname}.{part.removeprefix("@")}')
                if alias is not None:
                    inherit(alias)
                    node = model.relations.get_node(f'{table.fullname}.{part}')
            if node is None:
                # Unsupported/deferred paths retain their existing compile-time error.
                return None
            attrs = node.attr
            table = model.table(attrs['one_relation'] if attrs['mode'] == 'O'
                                else attrs['many_relation'])
        name = parts[-1]
        return table.columns.get(name) or table.virtual_columns.get(name) or table.composites.get(name)

    def inherit(column):
        key = column.fullname
        if key in active or key in done:
            return forward.get(key)
        active.add(key)
        target = target_column(column.table, column.attributes['relation_path'])
        relation = None
        if target is not None:
            relation = forward.get(target.fullname)
            if target.tag == 'aliasColumn':
                relation = inherit(target)
        if (key in forward or relation is not None) and target is not None and not column.attributes.get('dtype'):
            column.attributes['dtype'] = target.dtype
        if key not in forward and relation is not None:
            _register_relation(model, column.table, column,
                               dict(to=relation['one_relation'], foreign_key=False))
            column.attributes['virtual'] = True
            forward[key] = model.relations.get_node(f'{key.rsplit(".", 1)[0]}.@{column.name}').attr
        active.remove(key)
        done.add(key)
        return forward.get(key)

    for column in aliases.values():
        inherit(column)


class RelationTreeResolver(BagResolver):
    """Load one table at a time; descendants remain BagResolver instances."""

    class_kwargs = dict(cache_time=0, read_only=True, main_tbl=None, tbl_name=None,
                        pkg_name=None, path=None, parentpath=None)

    def __init__(self, *, model, **kwargs):
        self._model = model
        super().__init__(**kwargs)

    def load(self):
        model = self._model
        table = model.table(self.tbl_name, self.pkg_name)
        path = self.path or []
        parentpath = self.parentpath or []
        prefix = None
        if path:
            namespace = self.pkg_name + '_'
            prefix = '_'.join(part.removeprefix(namespace) for part in path
                              if part not in ('*O', '*M', '*m'))
        result = Bag()
        result.tbl_name = self.tbl_name
        result.pkg_name = self.pkg_name
        relations = model.relations.get_item(table.fullname)
        nodes = list(relations) if relations is not None else []
        one = {n.attr['many_relation']: n for n in nodes if n.attr['mode'] == 'O'}
        physical = list(table.columns.values())
        virtual = [*table.virtual_columns.values(), *table.composites.values()]
        for column in [*physical, *virtual]:
            attributes = dict(column.attributes, dtype=column.dtype)
            if column in physical:
                result.set_item(column.name, None, _attributes=deepcopy(attributes),
                                prfx=prefix, table=table.name, pkg=table.pkg.name)
            node = one.get(f'{table.fullname}.{column.name}')
            if node is None:
                continue
            pkg, name = node.attr['one_relation'].split('.')[:2]
            child = self._child(pkg, name, path + ['*O', f'{pkg}_{name}'], parentpath + [column])
            result.set_item(node.label, child, _attributes=deepcopy(attributes),
                            joiner=deepcopy(dict(node.attr)))
        for node in nodes:
            if node.attr['mode'] != 'M':
                continue
            pkg, name, column = node.attr['many_relation'].split('.')
            mode = '*M' if len(physical) == 1 and physical[0].name.endswith('_id') else '*m'
            child = self._child(pkg, name, path + [mode, f'{pkg}_{name}'], parentpath + [column])
            result.set_item(node.label, child, joiner=deepcopy(dict(node.attr)))
        return result

    def _child(self, pkg, table, path, parentpath):
        return type(self)(model=self._model, main_tbl=self.main_tbl, pkg_name=pkg,
                          tbl_name=table, path=path, parentpath=parentpath, cache_time=self.cache_time)
