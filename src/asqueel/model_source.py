"""Compose defaults and collect semantic sections before model resolution."""
from __future__ import annotations

from copy import deepcopy
import inspect
from genro_toolbox import extract_kwargs

from .configuration import _copy_recipe, _validate_source_shape
from .model_sections import Declaration, Option, Package, Schema


def attributes(node):
    return deepcopy({key: value for key, value in node.attr.items() if key != '_meta'})


def declaration(node):
    return Declaration(node.node_tag, node.get_attr('name') or node.label, attributes(node),
                       tuple(declaration(child) for child in node.value or ()))


@extract_kwargs(validate=True)
def column_declarations(node, *, validate_kwargs=None, **attrs):
    """Extract flat validation attributes only when translating the source."""
    children = tuple(declaration(child) for child in node.value or ())
    rules = dict(validate_kwargs)
    for child in children:
        if child.kind == 'validation':
            rules.update(child.attributes)
    result = tuple(child for child in children if child.kind != 'validation')
    return result + ((Declaration('validation', 'validation', rules),) if rules else ())


def options(node):
    container = node.value.get_node('options') if node.value is not None else None
    if container is None:
        return {}
    return {child.label: Option(child.node_tag, attributes(child)) for child in container.value or ()}


def prepare_source(builder):
    builder = _copy_recipe(builder)
    _validate_source_shape(builder)
    for _, node in builder.source.query('#p,#n', deep=True):
        current = node
        administrative = False
        while current is not None:
            if current.node_tag == 'connection':
                administrative = True
                break
            current = current.parent_node
        if administrative:
            continue
        owner = node.parent_bag._builder if node._get_meta('subbuilder') else node._resolve_builder()
        info = owner._get_schema_info(node.node_tag)
        if node.node_tag in ('table', 'column', 'validation'):
            continue
        for key, (_, _, default) in (info.get('call_args_validations') or {}).items():
            if key not in node.attr and default is not inspect.Parameter.empty and default is not None:
                if node.node_tag == 'relation' and key == 'indexed' and not node.get_attr('foreign_key'):
                    continue
                node.attr[key] = deepcopy(default)
                node.attr.setdefault('_meta', {}).setdefault('signature_defaults', []).append(key)
    resolve_source_types(builder)
    from .model_expansion import expand_options
    expand_options(builder)
    resolve_source_references(builder)
    return builder


def sections(catalog):
    default_schema = 'main' if catalog.database.get_attr('implementation') == 'sqlite' else 'public'
    schemas = {name: Schema(name, node.get_attr('sqlname'), attributes(node), options(node))
               for name, node in catalog.schemas.items()}
    physical_names = [schema.physical_name for schema in schemas.values()]
    if len(set(physical_names)) != len(physical_names):
        raise ValueError('Duplicate physical schema name')
    packages = {}
    for name, node in catalog.packages.items():
        schema = node.get_attr('sqlschema') or default_schema
        schemas.setdefault(schema, Schema(schema, attributes={'implicit': True}))
        configured = options(node)
        requires = configured.get('requires')
        if requires:
            required = requires.attributes['packages']
            required = [required] if isinstance(required, str) else required
            missing = set(required) - catalog.packages.keys()
            if missing:
                raise ValueError(f'package {name}: missing required packages {sorted(missing)}')
        packages[name] = Package(name, schema, node.get_attr('sqlprefix'), attributes(node), configured,
                                 tuple(f'{p}.{t}' for p, t in catalog.tables if p == name))
    for (package, name), entry in catalog.tables.items():
        override = entry['node'].get_attr('sqlschema')
        if package in packages and override and override not in schemas:
            raise ValueError(f'{package}.{name}: sqlschema {override!r} is not derived from a package')
    return schemas, packages


def resolve_source_types(builder):
    """Package types are available before options inspect existing columns."""
    from .catalog import SqlModelCatalog
    from .elements import DTYPE
    from typing import get_args
    catalog = SqlModelCatalog(builder)
    known = set(get_args(DTYPE))
    for (namespace, table_name), entry in catalog.tables.items():
        pkg = catalog.packages.get(namespace)
        aliases = options(pkg) if pkg is not None else {}
        for name, column in entry['columns'].items():
            dtype = column.get_attr('dtype')
            if dtype is not None and dtype not in known:
                alias = aliases.get('type_' + dtype)
                if alias is None:
                    raise ValueError(f'{namespace}.{table_name}.{name}: unknown dtype {dtype!r}')
                defaults = {key: value for key, value in alias.attributes.items() if key != 'name'}
                column.attr.update({key: value for key, value in defaults.items() if key not in column.attr})
                column.attr['dtype'] = defaults['dtype']


def resolve_source_references(builder):
    """Resolve references after all option-generated structures are present."""
    from .catalog import SqlModelCatalog
    from .common import split_names
    resolve_source_types(builder)
    catalog = SqlModelCatalog(builder)
    sql_actions = {'cascade': 'CASCADE', 'restrict': 'RESTRICT', 'no_action': None,
                   'set_null': 'SET NULL', 'set_default': 'SET DEFAULT'}
    for (namespace, table_name), entry in catalog.tables.items():
        pkey = entry['node'].get_attr('pkey')
        if pkey in entry['composites']:
            entry['node'].attr['x_logical_pkey'] = pkey
            entry['node'].attr['pkey'] = entry['composites'][pkey].get_attr('columns')
        for path, owner, relation in entry['relations']:
            attrs = relation.attr
            if attrs.get('name'):
                attrs['x_name'] = attrs['name']
            if attrs.get('inverse'):
                attrs['back_reference'] = attrs['inverse']
            target = attrs['to'].split('.')
            if len(target) == 2 and target[0] not in catalog.packages and (namespace, target[0]) in catalog.tables:
                attrs['to'] = namespace + '.' + attrs['to']
            if attrs.get('x_canonical'):
                for action in ('on_delete', 'on_update'):
                    value = attrs.get(action)
                    if value is not None and value not in ('CASCADE', 'RESTRICT', 'SET NULL', 'SET DEFAULT'):
                        if value not in ('raise', 'cascade', 'set_null', 'ignore'):
                            raise ValueError(f'{path}: invalid application action {value!r}')
                        attrs['x_app_' + action] = attrs.pop(action)
                    sql_key = action + '_sql'
                    sql_value = attrs.get(sql_key)
                    if action == 'on_update' and sql_key not in attrs and attrs.get('foreign_key'):
                        sql_value = 'cascade'
                    if sql_value is not None:
                        normalized_action = sql_value.lower().replace(' ', '_')
                        if normalized_action not in sql_actions:
                            raise ValueError(f'{path}: invalid SQL action {sql_value!r}')
                        attrs[action] = sql_actions[normalized_action]
                # onDuplicate is opaque legacy data (including False and recursive).
                defaults = (attrs.get('_meta') or {}).get('signature_defaults', ())
                if ('deferred' not in attrs or 'deferred' in defaults) and (
                        attrs.get('x_app_on_delete') == 'set_null' or attrs.get('on_delete') == 'SET NULL'):
                    attrs['deferred'] = True
    # Repeat for chains of inferred foreign-key columns (forward references).
    for _ in range(len(catalog.relations) + 1):
        changed = False
        for path, relation in catalog.relations:
            owner = relation.parent_node
            if owner.node_tag != 'column':
                continue
            parts = relation.get_attr('to').split('.')
            target = catalog.tables.get(tuple(parts[:2]))
            if target is None:
                continue  # The domain validator reports the full path.
            names = parts[2:] or split_names(target['node'].get_attr('pkey'))
            if len(names) != 1 or names[0] not in target['columns']:
                continue
            remote = target['columns'][names[0]]
            dtype = remote.get_attr('dtype') or ('A' if remote.get_attr('size') else None)
            dtype = {'serial': 'L', 'serial4': 'I'}.get(dtype, dtype)
            if owner.get_attr('dtype') is None and dtype is not None:
                owner.attr['dtype'] = dtype
                if remote.get_attr('size') is not None and owner.get_attr('size') is None:
                    owner.attr['size'] = remote.get_attr('size')
                changed = True
            if relation.get_attr('x_weak') and relation.get_attr('indexed', True):
                owner.attr.setdefault('indexed', True)
                remote.attr.setdefault('indexed', True)
        if not changed:
            break


def require_write_capabilities(table):
    """Fail before hooks/I/O while execution of these declarations is deferred."""
    from .contracts import UnsupportedFeatureError
    fields = table.options.get('sys_fields')
    pending = bool(fields and fields.enabled) or table.attributes.get('x_expanded_legacy')
    pending = pending or any(option.enabled for option in table.options.values())
    pending = pending or any(any(d.kind != 'relation' for d in column.declarations) or any(column.attributes.get(key) is not None
        for key in ('default', 'default_from', 'sql_value', 'x_generation'))
        or column.attributes.get('read_only') or column.attributes.get('unmodifiable')
        for column in table.columns.values())
    pending = pending or any(any(key.startswith('x_app_') for key in relation.attributes)
                            for relation in table.relations.values())
    if pending:
        raise UnsupportedFeatureError(f'{table.key}: write execution for these declarations is not implemented')
