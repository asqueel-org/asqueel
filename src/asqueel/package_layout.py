"""Package folders in the legacy layout: ``main.py`` and ``model/<table>.py``.

The layout is provisional (user decision 2026-10-18). A ``package`` element
with ``path`` loads its folder into the composed source, so the model is built
from the same declarations a recipe writes. ``path`` stays in the source: the
objects renderer loads each table's ``Table`` class from it.
"""
from __future__ import annotations

from hashlib import sha1
import importlib.util
from pathlib import Path
import sys

from genro_bag import Bag

from .application_table import SqlTable
from .contracts import not_available


def _module_name(path, package_name):
    """One module name per file, so two folders with the same package name never share a module."""
    path = Path(path).resolve()
    return f'asqueel_layout_{package_name}_{path.stem}_{sha1(str(path).encode()).hexdigest()[:12]}'


def _module(path, name):
    """Execute ``path`` as module ``name``, registered in ``sys.modules`` as legacy imports do."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_package_layouts(builder):
    """Load every package folder of the source into its declarations."""
    packages = [node for _, node in builder.source.query('#p,#n', deep=True)
                if node.node_tag == 'package' and node.get_attr('path')]
    for node in packages:
        load_package_layout(node)


def _columns(node):
    """Every column node below ``node``."""
    for child in node.value if isinstance(node.value, Bag) else ():
        if child.node_tag == 'column':
            yield child
        else:
            yield from _columns(child)


def table_class(folder, package_name, table_name):
    """The runtime class of ``table_name``: the ``Table`` of ``model/<table_name>.py`` over ``SqlTable``.

    Legacy binds the mixin by module name. A table without a module is a plain ``SqlTable``.
    """
    path = Path(folder) / 'model' / f'{table_name}.py'
    if not path.exists():
        return SqlTable
    name = _module_name(path, package_name)
    module = sys.modules.get(name) or _module(path, name)
    return type(table_name, (module.Table, SqlTable), {'__module__': name})


def load_package_layout(pkg):
    """Package attributes and custom types from ``main.py``, tables from ``model/``.

    Attributes written on the element win over ``config_attributes()``. Tables
    run their ``config_db`` in alphabetical order of their module names. Each
    ``custom_type_<dtype>()`` gives the column attributes of ``dtype='<dtype>'``,
    explicit column attributes winning, as legacy ``columns.py``.
    """
    folder = Path(pkg.get_attr('path'))
    name = pkg.get_attr('name') or pkg.label
    main = _module(folder / 'main.py', _module_name(folder / 'main.py', name))
    if hasattr(main, 'Table'):
        raise not_available(f'{name}: main.py Table, the mixin of every table of the package,')
    package = main.Package()
    for method in dir(package):
        if method == 'config_db' or method.startswith('config_db_') or method == 'onBuildingDbobj':
            raise not_available(f'{name}: Package.{method}')
    config_attributes = getattr(package, 'config_attributes', dict)
    for key, value in config_attributes().items():
        pkg.attr.setdefault(key, value)
    for path in sorted((folder / 'model').glob('*.py')):
        table_class = _module(path, _module_name(path, name)).Table
        for method in dir(table_class):
            if method.startswith('config_db_'):
                raise not_available(f'{name}.{path.stem}: {method}')
        table_class().config_db(pkg)
        tables = pkg.value.get_node('tables') if pkg.value is not None else None
        table = tables.value.get_node(path.stem) if tables is not None else None
        if table is None:
            raise ValueError(f'{name}: model/{path.name} declares no table {path.stem!r}; '
                             'a model module declares the table named after it')
    custom_types = {method.removeprefix('custom_type_'): getattr(package, method)()
                    for method in dir(package) if method.startswith('custom_type_')}
    for dtype, defaults in custom_types.items():
        if 'dtype' not in defaults:
            raise ValueError(f'{name}: Package.custom_type_{dtype}() returns no dtype')
    for column in _columns(pkg):
        defaults = custom_types.get(column.get_attr('dtype'))
        if defaults is not None:
            added = {key: value for key, value in defaults.items()
                     if key != 'dtype' and column.get_attr(key) is None}
            builder, where = column._resolve_builder(), column.parent_bag
            checked = dict(added, name=column.label)
            builder._missing_feature_attributes(where, 'column', checked)
            builder._legacy_column_attributes(where, checked)
            checked.pop('name')
            column.attr.update(checked, dtype=defaults['dtype'])
