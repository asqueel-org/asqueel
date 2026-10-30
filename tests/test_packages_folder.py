"""A packages folder: each subfolder is a package in the legacy layout."""
import textwrap

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig

MAIN = '''
class Package:
    def config_attributes(self):
        return dict(sqlschema='main', sqlprefix=False)
'''

CUSTOMER = '''
class Table:
    def config_db(self, pkg):
        tbl = pkg.table('customer', pkey='id')
        tbl.column('id', dtype='serial')
        tbl.column('name')
'''

CONTACT = '''
class Table:
    def config_db(self, pkg):
        tbl = pkg.table('contact', pkey='id')
        tbl.column('id', dtype='serial')
        tbl.column('customer_id', dtype='L').relation('sales.customer.id')
'''


def write_package(folder, **tables):
    (folder / 'model').mkdir(parents=True)
    (folder / 'main.py').write_text(textwrap.dedent(MAIN))
    for name, source in tables.items():
        (folder / 'model' / f'{name}.py').write_text(textwrap.dedent(source))


def write_packages(tmp_path):
    folder = tmp_path / 'packages'
    write_package(folder / 'sales', customer=CUSTOMER)
    write_package(folder / 'crm', contact=CONTACT)
    return folder


def config(tmp_path, folder):
    config = SqlDatabaseConfig()
    root = config.source.db('folder', implementation='sqlite')
    root.connection('main', database=str(tmp_path / 'folder.sqlite'))
    return config, root.packages(path=str(folder))


def test_each_subfolder_is_a_package_with_its_tables(tmp_path):
    folder = write_packages(tmp_path)
    model = AsqueelDb(config(tmp_path, folder)[0]).model
    assert sorted(model.packages) == ['crm', 'sales']
    assert model.table('sales.customer').column('name') is not None
    assert model.table('crm.contact').column('customer_id') is not None


def test_pycache_dot_folders_and_files_are_not_packages(tmp_path):
    folder = write_packages(tmp_path)
    (folder / '__pycache__').mkdir()
    (folder / '.git').mkdir()
    (folder / 'README.md').write_text('packages\n')
    model = AsqueelDb(config(tmp_path, folder)[0]).model
    assert sorted(model.packages) == ['crm', 'sales']


def test_a_recipe_package_composes_with_its_folder(tmp_path):
    folder = write_packages(tmp_path)
    source, packages = config(tmp_path, folder)
    packages.package('sales', name_long='Sales')
    model = AsqueelDb(source).model
    assert model.package('sales').attributes['name_long'] == 'Sales'
    assert model.table('sales.customer') is not None


def test_a_recipe_package_with_another_path_is_an_error(tmp_path):
    folder = write_packages(tmp_path)
    source, packages = config(tmp_path, folder)
    packages.package('sales', path=str(tmp_path / 'elsewhere'))
    with pytest.raises(ValueError, match="'sales' is declared with path"):
        AsqueelDb(source)


def test_a_subfolder_without_main_is_an_error(tmp_path):
    folder = write_packages(tmp_path)
    (folder / 'billing' / 'model').mkdir(parents=True)
    with pytest.raises(ValueError, match="'billing' has no main.py"):
        AsqueelDb(config(tmp_path, folder)[0])
