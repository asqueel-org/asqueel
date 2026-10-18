"""Compose defaults and collect semantic sections before model resolution."""
from __future__ import annotations

from copy import deepcopy
import inspect
from genro_toolbox import extract_kwargs

from .common import in_attribute_family
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


def generate_attributes(builder, node, attributes):
    """Write attributes for ``node``; those outside its grammar are recorded as generated.

    The domain validator accepts a key outside the grammar only when it is
    recorded here: a user who writes the same key by hand still gets the error.
    """
    declared = builder._get_schema_info(node.node_tag).get('declared_names') or set()
    node.attr.update(attributes)
    generated = {key for key in attributes if key not in declared
                 and not in_attribute_family(builder, node.node_tag, key)}
    if generated:
        meta = dict(node.attr.get('_meta') or {})
        meta['generated_attributes'] = sorted(set(meta.get('generated_attributes', ())) | generated)
        node.attr['_meta'] = meta


def prepare_source(builder, *, options_first=False):
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
    expand_options(builder, options_first=options_first)
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
        for name, column in entry['family'].items():
            dtype = column.get_attr('dtype')
            if dtype is not None and dtype not in known:
                alias = aliases.get('type_' + dtype)
                if alias is None:
                    raise ValueError(f'{namespace}.{table_name}.{name}: unknown dtype {dtype!r}')
                defaults = {key: value for key, value in alias.attributes.items() if key != 'name'}
                column.attr.setdefault('_meta', {})['type_defaults'] = list(defaults)
                column.attr.update({key: value for key, value in defaults.items() if key not in column.attr})
                column.attr['dtype'] = defaults['dtype']


def resolve_source_references(builder):
    """Resolve references after all option-generated structures are present."""
    from .catalog import SqlModelCatalog
    from .common import SQL_ACTIONS, split_names
    resolve_source_types(builder)
    catalog = SqlModelCatalog(builder)
    for (namespace, table_name), entry in catalog.tables.items():
        pkey = entry['node'].get_attr('pkey')
        if pkey in entry['composites']:
            entry['node'].attr['x_logical_pkey'] = pkey
            entry['node'].attr['pkey'] = entry['composites'][pkey].get_attr('columns')
        for path, owner, relation in entry['relations']:
            attrs = relation.attr
            if attrs.get('name'):
                attrs['x_name'] = attrs['name']
            target = attrs['to'].split('.')
            if len(target) == 2 and target[0] not in catalog.packages and (namespace, target[0]) in catalog.tables:
                attrs['to'] = namespace + '.' + attrs['to']
            if attrs.get('x_canonical'):
                column = relation.parent_node
                group = column.get_attr('group')
                if attrs.get('one_group') is None and group and group != '_':
                    # DbModelSrc.relation moves the FK display group to the
                    # one-side relation unless one_group was supplied.
                    attrs['one_group'] = group
                    generate_attributes(builder, column, {'group': '_', 'one_group': group})
            # onDuplicate is opaque legacy data (including False and recursive).
            defaults = (attrs.get('_meta') or {}).get('signature_defaults', ())
            if ('deferred' not in attrs or 'deferred' in defaults) and (
                    str(attrs.get('onDelete') or '').lower().startswith('setnull')
                    or SQL_ACTIONS.get(str(attrs.get('onDelete_sql')).lower()) == 'SET NULL'):
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
        if not changed:
            break
    # Weak relations have no FK but the legacy model indexes their physical
    # ends. Do this after inference, including composite owners, once only.
    for _, relation in catalog.relations:
        if not relation.get_attr('x_weak') or not relation.get_attr('indexed', True):
            continue
        owner = relation.parent_node
        if owner.node_tag not in ('column', 'compositeColumn'):
            continue  # A virtual scalar must not become a physical index.
        parts = relation.get_attr('to').split('.')
        target = catalog.tables.get(tuple(parts[:2]))
        if target is None:
            continue
        names = parts[2:] or split_names(target['node'].get_attr('pkey'))
        remote = target['family'].get(names[0]) if len(names) == 1 else None
        for column in (owner, remote):
            if column is None:
                continue
            if column.node_tag == 'compositeColumn':
                if not column.get_attr('unique'):
                    table = column.parent_node.parent_node
                    members = split_names(column.get_attr('columns'))
                    existing = [idx for idx in table.value.get_item('indexes') or ()
                                if split_names(idx.get_attr('columns')) == members]
                    if existing:
                        if any(idx.get_attr('where') or idx.get_attr('method') not in (None, 'btree')
                               for idx in existing):
                            raise ValueError(f'{table.label}: partial/non-btree index cannot cover weak relation {members}')
                    else:
                        table.index(columns=column.get_attr('columns'))
            elif column.node_tag == 'column':
                defaults = (column.attr.get('_meta') or {}).get('signature_defaults', ())
                if 'indexed' not in column.attr or 'indexed' in defaults:
                    column.attr['indexed'] = True


def require_write_capabilities(table):
    """Refuse the write cycle, before hooks and I/O, while a declaration is not executed.

    ``table`` is a DbTableObj. Each implementation step removes what it executes.
    """
    from .contracts import UnsupportedFeatureError
    executed = {'sys_fields'}
    enabled = {name for name, option in table.options.items() if option.attributes.get('enabled', True)}
    pending = [f'option {name}' for name in enabled if name not in executed]
    if table.attributes.get('x_expanded_legacy'):
        pending.append('legacy expansion')
    for name, column in table.columns.items():
        pending.extend(f'{name}.{child.tag}' for child in column.values() if child.tag != 'relation')
        attributes = column.attributes
        # checkPkey generates the sys_fields key.
        sys_key = ('sys_fields' in enabled and name == 'id'
                   and attributes.get('x_generation') == {'type': 'uuid', 'algorithm': 'legacy22'})
        pending.extend(f'{name}.{key}' for key in ('default', 'default_from', 'x_generation')
                       if attributes.get(key) is not None and not (sys_key and key == 'x_generation'))
        pending.extend(f'{name}.{key}' for key in ('read_only', 'unmodifiable')
                       if attributes.get(key) and not (sys_key and key == 'read_only'))
    if pending:
        raise UnsupportedFeatureError(
            f'{table.fullname}: write execution of {", ".join(pending)} is not available in this release')
