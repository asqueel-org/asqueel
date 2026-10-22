"""Grammar review using real test_invoice_pg models, not the full 75-table port.

Only selected declarations are shown; object rendering is not performed.
"""
from genro_bag.resolvers import EnvResolver
from asqueel import SqlDatabaseConfig


def source():
    config = SqlDatabaseConfig()
    db = config.source.db('test_invoice_pg', implementation='postgres')
    db.connection('main', database='test_invoice_pg',
                  host=EnvResolver('PGHOST', default='localhost'),
                  port=EnvResolver('PGPORT', default=5432, dtype='L'),
                  user=EnvResolver('PGUSER'), password=EnvResolver('PGPASSWORD'))
    packages = db.packages()
    sys = packages.package('sys', sqlschema='sys', sqlprefix=True)
    adm = packages.package('adm', sqlschema='adm', sqlprefix=True)
    invc = packages.package('invc', sqlschema='invc', sqlprefix=True)
    adm.options().requires('sys')
    invc.options().type('money', dtype='N', size='14,2')
    invc.options().type('perc', dtype='N', size='5,2')

    service = sys.table('service', pkey='service_identifier',
                        pkey_columns='service_type,service_name', name_long='Servizio',
                        name_short='Serv.', name_plural='Servizi', caption_field='service_identifier')
    service.options().sys_fields(id=False, user_upd=False)
    service.column('service_identifier', size=':60')
    service.column('service_type', size=':30')
    service.column('service_name', size=':30')
    service.column('parameters', dtype='X')

    # AttachmentTable belongs to adm, not to a fabricated invc.invoice_atc.
    template = adm.table('htmltemplate', pkey='id')
    template.options().sys_fields(user_upd=False)
    attachments = adm.table('htmltemplate_atc', pkey='id')
    attachments.options().attachments(master='adm.htmltemplate')
    counter = adm.table('counter', pkey='codekey', pkey_columns='pkg,tbl,code,fld,period')
    counter.options().sys_fields(id=False, user_upd=False)
    counter.column('codekey', size=':80')
    for name, size in (('pkg', ':12'), ('tbl', ':30'), ('code', ':12'),
                       ('fld', ':30'), ('period', ':10')):
        counter.column(name, size=size)

    customer = invc.table('customer', pkey='id', name_long='Cliente',
                         name_short='Cli.', name_plural='Clienti', caption_field='account_name',
                         partition_state='invc_state')
    customer.options().sys_fields(id={'type': 'uuid'}, draft=True,
                                  user_upd=False)
    customer.column('account_name', validate_notnull=True, validate_len='2:40')
    customer.column('state', size=':5').relation(
        'invc.state.code', foreign_key=True, relation_name='clients',
        onDelete='raise', onUpdate_sql='cascade')

    product_type = invc.table('product_type', pkey='id', name_long='Tipo prodotto',
                             name_short='Tipo', name_plural='Tipi prodotto',
                             caption_field='hierarchical_description')
    product_type.options().sys_fields(user_upd=False)
    product_type.options().hierarchical('description')
    product_type.options().auto_counter()
    product_type.options().dynamic_fields()
    product_type.column('description', size=':50')

    invoice = invc.table('invoice', pkey='id', name_long='Fattura',
                        name_short='Fatt.', name_plural='Fatture', caption_field='inv_number',
                        partition_customer_state='invc_state')
    invoice.options().sys_fields(user_upd=False)
    invoice.options().numbering('inv_number', parameters={
        'format': '$K$YY/$NNNNNN', 'code': 'A', 'period': 'YY',
        'date_field': 'date', 'showOnLoad': True, 'recycle': True})
    invoice.column('inv_number', size='10', unique=True)
    invoice.column('customer_id', size='22').relation(
        'invc.customer.id', foreign_key=True, relation_name='invoices',
        onDelete='raise', onUpdate_sql='cascade')
    # Legacy defaultValues supplies workdate during writes, outside this example.
    invoice.column('date', dtype='D', validate_notnull=True)
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
    row.options().sys_fields(user_upd=False)
    row.options().auto_counter('invoice_id')
    row.column('invoice_id', size='22').relation(
        'invc.invoice.id', foreign_key=True, relation_name='rows',
        onDelete='cascade', onUpdate_sql='cascade')
    row.column('product_id', size='22').relation(
        'invc.product.id', foreign_key=True, onDelete='raise', onUpdate_sql='cascade')
    row.column('quantity', dtype='I')
    row.column('unit_price', dtype='money')
    row.aliasColumn('product_name', relation_path='@product_id.description')
    row.formulaColumn('line_total', sql_formula='$quantity * $unit_price', dtype='N')
    row.virtualRelation('customer', relation='@invoice_id.@customer_id')

    config.validate_source()
    return config
