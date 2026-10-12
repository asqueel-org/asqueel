"""Source grammar example only. No expansion, connections or live objects."""
from asqueel import SqlDatabaseConfig


def source():
    config = SqlDatabaseConfig()
    db = config.source.db('invoice', implementation='postgresql')
    db.options().context('workdate', 'D', required=True)
    db.schemas().schema('business', name_long='Dati applicativi').options().metadata(
        'documentation', {'owner': 'Accounting'})
    packages = db.packages()
    packages.package('sys', sqlschema='business')
    pkg = packages.package('invc', sqlschema='business')
    pkg.options().requires('sys')
    pkg.options().type('money', dtype='N', size='14,2')
    customer = pkg.table('customer', pkey='id', name_long='Cliente', name_short='Cli.',
                         name_plural='Clienti', caption_field='account_name')
    customer.options().sys_fields(id={'type': 'uuid'}, user_upd=False)
    customer.options().behavior('invc.customer')
    customer.options().partition('state', field='state', context='invc_state')
    customer.column('account_name', validate_notnull=True, validate_len='2:40')
    customer.column('state', size='0:5')
    customer.column('bank_account').encryption(mode='R', provider='security.encryption')
    customer.column('details', dtype='X').dynamic_fields(source='invc.product_type.df_fields')

    product_type = pkg.table('product_type', pkey='id')
    product_type.options().sys_fields(user_upd=False)
    product_type.options().hierarchical(columns=[{'name': 'code', 'unique': True}])
    product_type.options().auto_counter(scope='parent_id')
    product_type.options().dynamic_fields(templates={'default': 'product.template'})
    product_type.column('code', dtype='T')

    invoice = pkg.table('invoice', pkey='id')
    opts = invoice.options()
    opts.sys_fields(user_upd=False)
    opts.audit('full', provider='accounting.audit')
    opts.numbering('inv_number', provider='accounting.numbering', parameters={'yearly': True})
    opts.broadcast('id', 'inv_number', provider='events.invoice')
    opts.retention(field='date', days=3650, provider='storage.retention')
    opts.archive(provider='storage.archive')
    opts.enabled_when(preference='invoice.enabled', provider='application.preferences')
    opts.protection(rules=['invoice.protection'], tag='accounting')
    opts.diagnostics(rules=['invoice.consistency'], invalid_fields=True,
                     invalid_relations=['@rows'])
    opts.record_hash(columns=['inv_number', 'date'])
    opts.full_update()
    opts.release(handlers={'1': 'invoice.upgrade_v1'})
    invoice.column('inv_number', dtype='T')
    invoice.column('date', dtype='D')

    pkg.table('invoice_atc', pkey='id').options().attachments(
        master='invc.invoice', provider='storage.attachments')
    settings = pkg.table('settings', pkey='code')
    settings.options().pkey_from(['area', 'name'], missing='error')
    settings.options().system_records(records={'default': {'name': 'Standard'}})
    settings.options().tenant(context='tenant_id', provider='application.tenant')
    settings.column('code', dtype='T')
    settings.column('area', dtype='T')
    settings.column('name', dtype='T')
    row = pkg.table('invoice_row')
    row.options().relative_index('invoice_id')
    row.column('invoice_id').relation('invc.invoice.id')
    config.validate_source()
    return config
