"""Hierarchical SQL model objects built from renderer fragments, not descriptors.

The construction order follows GnrStructObj: initialize the parent, build its
children, then complete the parent. Model-wide relations are registered only
once every table exists. There is no compiler or connection in this module.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from genro_bag import Bag
from genro_toolbox import extract_kwargs

from .application_table import SqlTable
from .common import default_index_name, indexed_attributes, package_sqlschema, split_names, table_sqlname, unknown_indexed_keys
from .hierarchical import HierarchicalHandler
from .package_layout import table_class as layout_table_class


@dataclass(frozen=True)
class _Fragment:
    name: str
    tag: str
    attributes: dict
    children: tuple[_Fragment, ...]
    node: Any = None
    physical_column: bool = False


class DbModelObj:
    """A source node with legacy parent/root/children and attribute lookup."""

    def __init__(self, fragment, *, model, parent=None):
        self.name, self.tag = fragment.name, fragment.tag
        self.attributes = deepcopy(fragment.attributes)
        self.structnode = fragment.node
        self.parent = parent
        self._model = model
        self.children: dict[str, DbModelObj] = {}
        if parent is None:
            self.rootparent = model
        self.doInit()
        for child in fragment.children:
            obj = _object_class(child)(child, model=model, parent=self)
            if obj.name.lower() in self.children:
                raise ValueError(f'Duplicate child {obj.name!r} in {self.name}')
            self.children[obj.name.lower()] = obj
        self.afterChildrenCreation()

    def doInit(self):
        pass

    def afterChildrenCreation(self):
        pass

    @property
    def root(self):
        return self.parent.root if self.parent is not None else self

    @property
    def db(self):
        return self._model.db

    dbroot = db

    @property
    def pkg(self):
        node = self
        while node is not None and node.tag != 'package':
            node = node.parent
        return node

    @property
    def table(self):
        node = self
        while node is not None and node.tag != 'table':
            node = node.parent
        return node

    @property
    def options(self):
        return self.get('options', {})

    @property
    def sqlname(self):
        return self.attributes.get('sqlname') or self.name

    @property
    def name_short(self):
        return self.attributes.get('name_short') or self.attributes.get('name_long') or self.name

    @property
    def name_long(self):
        return self.attributes.get('name_long') or self.name_short

    @property
    def name_full(self):
        return self.attributes.get('name_full') or self.name_long

    def getAttr(self, name=None, dflt=None):
        return self.attributes.get(name, dflt) if name else self.attributes

    def get(self, name, default=None):
        return self.children.get(name.lower(), default)

    def __getitem__(self, path):
        node = self.root if path.startswith('.') else self
        for name in path.lstrip('.').split('.'):
            node = node.get(name) if node is not None else None
        return node

    def __bool__(self):
        return True

    def __len__(self):
        return len(self.children)

    # Lookup is case-insensitive; iteration gives the declared names.
    def __contains__(self, name):
        return isinstance(name, str) and name.lower() in self.children

    def __iter__(self):
        return iter(self.keys())

    def keys(self):
        return {obj.name: obj for obj in self.children.values()}.keys()

    def values(self):
        return self.children.values()

    def items(self):
        return {obj.name: obj for obj in self.children.values()}.items()


class DbPackageObj(DbModelObj):
    @property
    def tables(self):
        return self.get('tables', {})

    def table(self, name):
        found = self.tables.get(name)
        if found is None:
            raise ValueError(f'Unknown table {self.name}.{name}')
        return found

    @property
    def sqlschema(self):
        return package_sqlschema(self.attributes, self._model.implementation)

    def tableSqlName(self, table):
        return table_sqlname(self.name, self.attributes, table.name, {})


class DbTableObj(DbModelObj):
    def doInit(self):
        # Legacy _getMixinObj creates the operational table before its children.
        # Only the Table class of the package layout is installed.
        path = self.pkg.attributes.get('path')
        table_class = layout_table_class(path, self.pkg.name, self.name) if path else SqlTable
        self._check_table_methods(table_class)
        self.dbtable = table_class(self)
        self._relation_tree = None

    def _check_table_methods(self, table_class):
        """Refuse legacy package triggers (``trigger_on<Event>_<pkg>``)."""
        from .contracts import UnsupportedFeatureError
        from .table_triggers import TriggersMixin
        hooks = [name for name in vars(TriggersMixin) if name.startswith('trigger_on')]
        for name in dir(table_class):
            if any(name.startswith(hook + '_') for hook in hooks):
                raise UnsupportedFeatureError(
                    f'{self.fullname}: table method {name!r} is not available in this release')

    def afterChildrenCreation(self):
        # DbTableObj.afterChildrenCreation, restricted to admitted containers.
        for name in ('columns', 'virtual_columns', 'indexes'):
            if name not in self.children:
                self.children[name] = DbModelObj(_Fragment(name, name, {}, ()), model=self._model, parent=self)
        for column in self.columns.values():
            indexed = column.attributes.get('indexed')
            if column.attributes.get('unique'):
                self._column_index(column.name, unique=True)
            elif indexed:
                unknown = unknown_indexed_keys(indexed)
                if unknown:
                    from .validators import SqlModelValidationError
                    raise SqlModelValidationError([f"{column.fullname}: unknown indexed option(s) {', '.join(unknown)}"])
                # legacy fill_json_column_index: unique without where is the column's own UNIQUE.
                attributes = indexed_attributes([column.name], indexed)
                if attributes is not None:
                    self._column_index(column.name, **attributes)

        hierarchical = self.options.get('hierarchical')
        if hierarchical is not None and hierarchical.attributes.get('enabled', True):
            # Legacy table.py:82-83: the handler exists only on hierarchical tables.
            self.dbtable.hierarchicalHandler = HierarchicalHandler(self.dbtable)

    def _column_index(self, column, **attributes):
        name = default_index_name(self.name, column)
        if name not in self.indexes:
            fragment = _Fragment(name, 'index', {'columns': column, **attributes}, ())
            self.indexes.children[name] = DbIndexObj(fragment, model=self._model, parent=self.indexes)

    @property
    def fullname(self):
        return f'{self.pkg.name}.{self.name}'

    @property
    def columns(self):
        return self.get('columns', {})

    @property
    def virtual_columns(self):
        """Legacy virtual_columns: the declared ones plus the ``formulaColumn_<x>()`` objects, cached per environment."""
        container = self.get('virtual_columns', {})
        methods = [name for name in dir(self.dbtable) if name.startswith('formulaColumn_')]
        if not methods:
            return container
        key = '_virtual_columns_' + self.fullname.replace('.', '_')
        env = self.db.currentEnv
        if key in env:
            return env[key]
        for method in methods:
            declared = getattr(self.dbtable, method)()
            for attributes in declared if isinstance(declared, list) else [declared]:
                attributes = dict(attributes)
                name = attributes.pop('name')
                existing = container.get(name)
                if name in self.columns or name in self.composites or (existing is not None and existing.structnode is not None):
                    raise ValueError(f'{self.fullname}.{name}: {method}() redefines a declared column')
                container.children[name.lower()] = DbVirtualColumnObj(_Fragment(name, 'formulaColumn', attributes, ()),
                                                                      model=self._model, parent=container)
        env[key] = container
        return container

    @property
    def composites(self):
        return self.get('composites', {})

    @property
    def dynamic_columns(self):
        """The ``formulaColumn_<x>()`` objects of ``virtual_columns``, by lowercase name."""
        return {name: column for name, column in self.virtual_columns.items() if column.structnode is None}

    @property
    def indexes(self):
        return self.get('indexes', {})

    @property
    def pkey(self):
        return self.attributes.get('pkey')

    @property
    def sqlschema(self):
        return self.attributes.get('sqlschema') or self.pkg.sqlschema

    @property
    def sqlname(self):
        return self.attributes.get('sqlname') or self.pkg.tableSqlName(self)

    @property
    def pkeys(self):
        pkey = self.pkey
        if not pkey:
            return []
        composite = self.composites.get(pkey)
        return split_names(composite.attributes['columns']) if composite is not None else [pkey]

    def physical_columns(self, name):
        """Expand already-declared composite keys, preserving their identity."""
        column = self.column(name)
        if column.tag == 'compositeColumn':
            return tuple(split_names(column.attributes['columns']))
        return (name,)

    @property
    def lastTS(self):
        return self.attributes.get('lastTS') or ''

    @property
    def logicalDeletionField(self):
        return self.attributes.get('logicalDeletionField') or ''

    @property
    def draftField(self):
        return self.attributes.get('draftField') or ''

    @property
    def name_plural(self):
        return self.attributes.get('name_plural') or self.name_long

    def newRelationResolver(self, cacheTime=0):
        from .object_tree_relations import RelationTreeResolver
        return RelationTreeResolver(model=self._model, main_tbl=self.fullname,
                                    pkg_name=self.pkg.name, tbl_name=self.name, cache_time=cacheTime)

    @property
    def relations(self):
        if self._relation_tree is None:
            self._relation_tree = self.newRelationResolver(cacheTime=-1)()
        return self._relation_tree

    def column(self, name, *, _seen=None):
        """Resolve fields and @paths through the relation tree, as in legacy."""
        name = name.removeprefix('$')
        if name.startswith('@'):
            relation, _, rest = name.partition('.')
            node = self.relations.get_node(relation)
            if node is None or not rest:
                raise ValueError(f'Unknown column path {self.fullname}.{name}')
            joiner = node.attr['joiner']
            target = joiner['one_relation'] if joiner['mode'] == 'O' else joiner['many_relation']
            return self._model.table(target).column(rest, _seen=_seen)
        column = self.columns.get(name) or self.virtual_columns.get(name) or self.composites.get(name)
        if column is None:
            return None
        if column.tag == 'aliasColumn':
            seen = set() if _seen is None else set(_seen)
            key = self.fullname, name
            if key in seen:
                raise ValueError(f'Cyclic alias: {self.fullname}.{name}')
            seen.add(key)
            original = self.column(column.attributes['relation_path'], _seen=seen)
            if original is None:
                raise ValueError(f'Unknown column {self.fullname}.{column.attributes["relation_path"]}')
            return AliasColumnWrapper(original, column)
        return column



def _missing_feature(name):
    def refuse(self):
        from .contracts import not_available
        raise not_available(f'{self.fullname}: {name}')
    return property(refuse)


for _name in ('rowcaption', 'newrecord_caption', 'starColumns', 'getRelation', 'getJoiner',
              'relations_one', 'relations_many', 'manyRelationsList', 'relationExplorer'):
    setattr(DbTableObj, _name, _missing_feature(_name))

class DbColumnObj(DbModelObj):
    @property
    def fullname(self):
        return f'{self.table.fullname}.{self.name}'

    @property
    def dtype(self):
        return self.attributes.get('dtype') or ('A' if self.attributes.get('size') else 'T')

    @property
    def print_width(self):
        return self.attributes.get('print_width')

    @property
    def validations(self):
        @extract_kwargs(validate=True)
        def collect(*, validate_kwargs=None, **attrs):
            return validate_kwargs
        return deepcopy(collect(**self.attributes))


class DbVirtualColumnObj(DbColumnObj):
    @property
    def dtype(self):
        if self.tag == 'compositeColumn':
            return self.attributes.get('dtype') or 'JS'
        if self.tag == 'formulaColumn':
            return self.attributes.get('dtype') or 'A'
        return super().dtype

    def afterChildrenCreation(self):
        if any(child.tag == 'relation' for child in self.values()):
            self.attributes['virtual'] = True


class DbIndexObj(DbModelObj):
    @property
    def sqlname(self):
        columns = self.attributes['columns']
        names = ','.join(columns) if isinstance(columns, dict) else columns
        return self.attributes.get('sqlname') or f'{self.table.sqlname}_{names.replace(",", "_")}_idx'


class AliasColumnWrapper:
    """Legacy merged alias view; originalColumn remains in the owning tree."""

    def __init__(self, original, alias):
        self.originalColumn = original
        self.relation_path = alias.attributes['relation_path']
        self.attributes = dict(original.attributes)
        # Signature defaults must not hide the target's declared dtype.
        defaults = (alias.structnode.attr.get('_meta') or {}).get('signature_defaults', ())
        self.attributes.update({k: v for k, v in alias.attributes.items()
                                if k not in ('relation_path', 'tag') and k not in defaults})

    def __getattr__(self, name):
        return getattr(self.originalColumn, name)

    @property
    def dtype(self):
        return self.attributes.get('dtype') or self.originalColumn.dtype


def _object_class(fragment):
    if fragment.tag == 'package':
        return DbPackageObj
    if fragment.tag == 'table':
        return DbTableObj
    if fragment.tag == 'index':
        return DbIndexObj
    if fragment.physical_column:
        return DbColumnObj
    if fragment.tag in ('formulaColumn', 'aliasColumn', 'subQueryColumn', 'bagItemColumn',
                        'pyColumn', 'compositeColumn'):
        return DbVirtualColumnObj
    return DbModelObj


class DbModel:
    """Source-owned hierarchical model; relations are a global Bag, not edges."""

    def __init__(self, db):
        self.db = db
        self.relations = Bag()

    def build(self, fragment):
        """Build the objects of the rendered ``db`` fragment, parent before children, as legacy."""
        self.src = fragment.node.parent_bag
        self.implementation = fragment.attributes.get('implementation', 'sqlite')
        # Legacy model.obj is the namespace list, not the authored <db> node.
        # Database options remain on the database declaration, outside that root.
        namespaces = next((c for c in fragment.children if c.tag == 'packages'),
                          _Fragment('packages', 'packages', {}, ()))
        self.obj = DbModelObj(namespaces, model=self)
        self.name = fragment.attributes.get('name', fragment.name)
        from .object_tree_relations import build_relations
        build_relations(self)

    @property
    def packages(self):
        return self.obj if self.obj.tag == 'packages' else {}

    @property
    def tables(self):
        # This index exposes the very same objects; it is not a second model.
        return {table.fullname: table for pkg in self.obj.values() for table in pkg.tables.values()}

    def package(self, name):
        return self.packages.get(name)

    def table(self, name, pkg=None):
        if '.' in name:
            pkg, name = name.split('.')[:2]
        if pkg is None:
            raise ValueError(f'table() requires package.table: {name!r}')
        namespace = self.obj.get(pkg)
        return namespace.table(name) if namespace is not None else None

    def column(self, name):
        pkg, table, column = name.split('.', 2)
        found = self.table(table, pkg)
        if found is None:
            raise ValueError(f'Unknown package {pkg!r}')
        return found.column(column)

