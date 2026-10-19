"""Package folders in the legacy layout: ``main.py`` and ``model/<table>.py``.

The layout is provisional (user decision 2026-10-18). A ``package`` element
with ``path`` loads its folder into the composed source, so the model is built
from the same declarations a recipe writes.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from .contracts import not_available


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_package_layouts(builder):
    """Load every package folder of the source, replacing ``path`` with its declarations."""
    packages = [node for _, node in builder.source.query('#p,#n', deep=True)
                if node.node_tag == 'package' and node.get_attr('path')]
    for node in packages:
        load_package_layout(node)


def _columns(node):
    """Every column node below ``node``."""
    for child in node.value or ():
        if child.node_tag == 'column':
            yield child
        elif child.value is not None and hasattr(child.value, '__iter__') and not isinstance(child.value, str):
            yield from _columns(child)


def load_package_layout(pkg):
    """Package attributes and custom types from ``main.py``, tables from ``model/``.

    Attributes written on the element win over ``config_attributes()``. Tables
    run their ``config_db`` in alphabetical order of their module names; the
    ``Table`` class of ``model/<name>.py`` is the runtime class of table
    ``<name>``, as legacy binds the mixin by module name. Each
    ``custom_type_<dtype>()`` gives the column attributes of ``dtype='<dtype>'``,
    explicit column attributes winning, as legacy ``columns.py``.
    """
    from .application_table import SqlTable
    folder = Path(pkg.attr.pop('path'))
    name = pkg.get_attr('name') or pkg.label
    main = _module(folder / 'main.py', f'asqueel_layout_{name}')
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
        table_class = _module(path, f'asqueel_layout_{name}_{path.stem}').Table
        for method in dir(table_class):
            if method.startswith('config_db_'):
                raise not_available(f'{name}.{path.stem}: {method}')
        table_class().config_db(pkg)
        tables = pkg.value.get_node('tables') if pkg.value is not None else None
        table = tables.value.get_node(path.stem) if tables is not None else None
        if table is None:
            raise ValueError(f'{name}: model/{path.name} declares no table {path.stem!r}; '
                             'a model module declares the table named after it')
        table.attr['x_table_class'] = type(path.stem, (table_class, SqlTable), {})
    custom_types = {method.removeprefix('custom_type_'): getattr(package, method)()
                    for method in dir(package) if method.startswith('custom_type_')}
    for column in _columns(pkg):
        defaults = custom_types.get(column.get_attr('dtype'))
        if defaults is not None:
            column.attr['dtype'] = defaults.get('dtype')
            for key, value in defaults.items():
                if key != 'dtype' and column.get_attr(key) is None:
                    column.attr[key] = value
