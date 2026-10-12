"""Grammar review using real test_invoice_pg models, not the full 75-table port.

Only selected declarations are shown. Provider binding and object rendering are
not performed. workdate/current_state may be application callbacks.
"""
from genro_bag.resolvers import BagCbResolver, EnvResolver
from asqueel import SqlDatabaseConfig


def source(*, workdate=None, current_state=None):
    config = SqlDatabaseConfig()
    db = config.source.db('test_invoice_pg', implementation='postgresql')
    db.connection('main', database='test_invoice_pg',
                  host=EnvResolver('PGHOST', default='localhost'),
                  port=EnvResolver('PGPORT', default=5432, dtype='L'),
                  user=EnvResolver('PGUSER'), password=EnvResolver('PGPASSWORD'))
    schemas = db.schemas()
    for name in ('sys', 'adm', 'invc'):
        schemas.schema(name)
    packages = db.packages()
    sys = packages.package('sys', sqlschema='sys', sqlprefix=True)
    adm = packages.package('adm', sqlschema='adm', sqlprefix=True)
    invc = packages.package('invc', sqlschema='invc', sqlprefix=True)
    adm.options().requires('sys')
    invc.options().type('money', dtype='N', size='14,2')
    invc.options().type('perc', dtype='N', size='5,2')

    service = sys.table('service', pkey='service_identifier', name_long='Servizio',
                        name_short='Serv.', name_plural='Servizi', caption_field='service_identifier')
    service.options().sys_fields(id=False, user_upd=False, timestamp_type='DH')
    service.options().pkey_from(['service_type', 'service_name'], missing='skip')
    service.column('service_identifier', size=':60')
    service.column('service_type', size=':30')
    service.column('service_name', size=':30')
    service.column('parameters', dtype='X')

    # AttachmentTable belongs to adm, not to a fabricated invc.invoice_atc.
    template = adm.table('htmltemplate', pkey='id')
    template.options().sys_fields(user_upd=False, timestamp_type='DH')
    attachments = adm.table('htmltemplate_atc', pkey='id')
    attachments.options().attachments(master='adm.htmltemplate')
    counter = adm.table('counter', pkey='codekey')
    counter.options().sys_fields(id=False, user_upd=False, timestamp_type='DH')
    counter.options().tenant()
    counter.options().pkey_from('pkg,tbl,code,fld,period', missing='skip')
    counter.column('codekey', size=':80')
    for name, size in (('pkg', ':12'), ('tbl', ':30'), ('code', ':12'),
                       ('fld', ':30'), ('period', ':10')):
        counter.column(name, size=size)

    customer = invc.table('customer', pkey='id', name_long='Cliente',
                         name_short='Cli.', name_plural='Clienti', caption_field='account_name')
    customer.options().sys_fields(id={'type': 'uuid'}, draft=True,
                                  user_upd=False, timestamp_type='DH')
    state = (BagCbResolver(current_state) if current_state is not None
             else EnvResolver('INVC_STATE'))
    customer.options().partition('state', field='state', value=state)
    customer.column('account_name', validate_notnull=True, validate_len='2:40')
    customer.column('state', size=':5').relation(
        'invc.state.code', foreign_key=True, inverse='clients',
        on_delete='raise', on_update_sql='CASCADE')
    customer.column('bank_account').encryption(mode='R')

    product_type = invc.table('product_type', pkey='id', name_long='Tipo prodotto',
                             name_short='Tipo', name_plural='Tipi prodotto',
                             caption_field='hierarchical_description')
    product_type.options().sys_fields(user_upd=False, timestamp_type='DH')
    product_type.options().hierarchical('description')
    product_type.options().auto_counter('parent_id')
    product_type.options().dynamic_fields()
    product_type.column('description', size=':50')

    invoice = invc.table('invoice', pkey='id', name_long='Fattura',
                        name_short='Fatt.', name_plural='Fatture', caption_field='inv_number')
    invoice.options().sys_fields(user_upd=False, timestamp_type='DH')
    invoice.options().numbering('inv_number', parameters={
        'format': '$K$YY/$NNNNNN', 'code': 'A', 'period': 'YY',
        'date_field': 'date', 'showOnLoad': True, 'recycle': True})
    invoice.options().partition('customer_state', field='customer_state', value=state)
    invoice.column('inv_number', size='10', unique=True)
    invoice.column('customer_id', size='22').relation(
        'invc.customer.id', foreign_key=True, inverse='invoices',
        on_delete='raise', on_update_sql='CASCADE')
    date_value = (BagCbResolver(workdate) if workdate is not None
                  else EnvResolver('INVOICE_WORKDATE', dtype='D'))
    invoice.column('date', dtype='D', validate_notnull=True, default=date_value)
    invoice.column('total', dtype='money')
    invoice.aliasColumn('customer_state', relation_path='@customer_id.state')
    invoice.formulaColumn('row_count', select={
        'table': 'invc.invoice_row', 'columns': 'COUNT(*)',
        'where': '$invoice_id = #THIS.id'}, dtype='L')
    invoice.subQueryColumn('rows_json', query={
        'table': 'invc.invoice_row', 'columns': '$product_id,$quantity,$unit_price',
        'where': '$invoice_id = #THIS.id'}, mode='json')

    row = invc.table('invoice_row', pkey='id', name_long='Riga fattura',
                    name_short='Riga', name_plural='Righe fattura', caption_field='product_name')
    row.options().sys_fields(user_upd=False, timestamp_type='DH')
    row.options().auto_counter('invoice_id')
    row.column('invoice_id', size='22').relation(
        'invc.invoice.id', foreign_key=True, inverse='rows',
        on_delete='cascade', on_update_sql='CASCADE')
    row.column('product_id', size='22').relation(
        'invc.product.id', foreign_key=True, on_delete='raise', on_update_sql='CASCADE')
    row.column('quantity', dtype='I')
    row.column('unit_price', dtype='money')
    row.aliasColumn('product_name', relation_path='@product_id.description')
    row.formulaColumn('line_total', expression='$quantity * $unit_price', dtype='N')
    row.virtualRelation('customer', relation='@invoice_id.@customer_id')

    config.validate_source()
    return config
