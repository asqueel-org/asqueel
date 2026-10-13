"""Native test_invoice_pg source: 74 models, with the agreed exclusions."""
from asqueel import SqlDatabaseConfig
from . import sys, adm, invc


def source():
    config = SqlDatabaseConfig()
    db = config.source.db('test_invoice_pg', implementation='postgresql')
    packages = db.packages()
    sys_pkg = packages.package('sys', sqlschema='sys', comment='sys', name_short='System', name_long='System', name_full='System', x_legacy__syspackage=True)
    adm_pkg = packages.package('adm', sqlschema='adm', comment='Admin', name_short='Adm', name_long='!!Administration')
    invc_pkg = packages.package('invc', sqlschema='invc', sqlprefix=True, comment='invc package', name_short='Invc', name_long='Invoicer', name_full='Invc')
    adm_pkg.options().requires('sys')
    invc_pkg.options().type('money', dtype='N', size='14,2', x_ui_format='#,###.00')
    invc_pkg.options().type('perc', dtype='N', size='5,2', x_ui_format='##.00')
    sys.configure(sys_pkg)
    adm.configure(adm_pkg)
    invc.configure(invc_pkg)
    with config.contribution('adm:sys.task'):
        adm.sys_task_contribution(sys_pkg)
    config.validate_source()
    return config
