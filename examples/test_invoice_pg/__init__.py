"""Native test_invoice_pg source: 74 models, with the agreed exclusions.

Each package is a folder in the package layout, declared with its path.
"""
from pathlib import Path

from asqueel import SqlDatabaseConfig

PACKAGES = Path(__file__).resolve().parent / 'packages'


def source():
    config = SqlDatabaseConfig()
    db = config.source.db('test_invoice_pg', implementation='postgres')
    packages = db.packages()
    packages.package('sys', path=str(PACKAGES / 'sys'))
    adm_pkg = packages.package('adm', path=str(PACKAGES / 'adm'))
    invc_pkg = packages.package('invc', path=str(PACKAGES / 'invc'))
    adm_pkg.options().requires('sys')
    invc_pkg.options().type('money', dtype='N', size='14,2')
    invc_pkg.options().type('perc', dtype='N', size='5,2')
    config.validate_source()
    return config
