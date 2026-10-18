"""Package folders in the legacy layout: ``main.py`` and ``model/<table>.py``.

The layout is provisional (user decision 2026-10-18). A ``package`` element
with ``path`` loads its folder into the composed source, so the model is built
from the same declarations a recipe writes.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from .contracts import UnsupportedFeatureError


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_package_layouts(builder):  # wf:phase-4:new
    """Load every package folder of the source, replacing ``path`` with its declarations."""
    packages = [node for _, node in builder.source.query('#p,#n', deep=True)
                if node.node_tag == 'package' and node.get_attr('path')]
    for node in packages:
        load_package_layout(node)


def load_package_layout(pkg):  # wf:phase-4:new
    """Package attributes and custom types from ``main.py``, tables from ``model/``.

    Attributes written on the element win over ``config_attributes()``; each
    ``custom_type_<dtype>()`` becomes the package type ``<dtype>``; tables run
    their ``config_db`` in alphabetical order of their module names.
    """
    from .application_table import SqlTable
    folder = Path(pkg.attr.pop('path'))
    name = pkg.get_attr('name') or pkg.label
    package = _module(folder / 'main.py', f'asqueel_layout_{name}').Package()
    for key, value in package.config_attributes().items():
        pkg.attr.setdefault(key, value)
    for method in sorted(dir(package)):
        if method.startswith('custom_type_'):
            pkg.options().type(method.removeprefix('custom_type_'), **getattr(package, method)())
    for path in sorted((folder / 'model').glob('*.py')):
        table_class = _module(path, f'asqueel_layout_{name}_{path.stem}').Table
        for method in dir(table_class):
            if method.startswith('config_db_'):
                raise UnsupportedFeatureError(
                    f'{name}.{path.stem}: {method} is not available in this release')
        tables = pkg.value.get_node('tables') if pkg.value is not None else None
        before = set(tables.value.keys()) if tables is not None else set()
        table_class().config_db(pkg)
        for table in pkg.value.get_node('tables').value:
            if table.label not in before:
                table.attr['x_table_class'] = type(table.label, (table_class, SqlTable), {})
