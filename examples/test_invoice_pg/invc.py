"""Native declarations transcribed from original config_db methods.

No GenroPy imports or expanded legacy fixtures are needed.
"""


# projects/test_invoice/packages/invc/model/customer.py
# SHA256: f3f76a6c57c6682502afabe328b5e18d9ff418efabdb56e36b7623c2ce5c45b4
def customer(pkg):
    tbl = pkg.table('customer', pkey='id', name_long='!!Customer', name_plural='!!Customers', caption_field='account_name',
                    partition_state='invc_state')
    tbl.options().sys_fields(draft=True, user_upd=False, group_name='!![en]System')
    tbl.column('account_name', name_long='!!Account name', name_short='Account name', validate_notnull=True, validate_len='2:40', group='001')
    tbl.column('street_address', name_long='!!Street Address', name_short='St.Address', group='b_address.01')
    tbl.column('suburb', name_long='!!Suburb', name_short='!!Suburb', group='b_address.02')
    tbl.column('state', size=':5', name_long='!!State', name_short='Pr.', group='b_address.04').relation('invc.state.code', relation_name='clients', onDelete='raise', one_group='b_address.04', foreign_key=True)
    tbl.column('postcode', size=':5', name_long='!!Postcode', name_short='Postcode', group='b_address.03')
    tbl.column('customer_type_code', size=':5', name_long='!!Customer type code', name_short='!!Cust type', group='002').relation('customer_type.code', relation_name='customers', onDelete='raise', one_group='002', foreign_key=True)
    tbl.column('payment_type_code', size=':10', name_long='!!Payment type code', name_short='!!Pay type', group='d_billing.01').relation('payment_type.code', relation_name='customers', onDelete='raise', one_group='d_billing.01', foreign_key=True)
    tbl.column('notes', name_long='!!Notes', group='y_other.01')
    tbl.column('email', name_long='!!Email', group='c_contacts.01')
    tbl.column('phone', name_long='!!Phone', group='c_contacts.02')
    tbl.column('access_token', name_long='!!Access Token', group='_')
    tbl.column('bank_account', name_long='!!Bank Account', group='d_billing.03')
    tbl.column('registration_id', name_long='!!Registration ID', group='d_billing.04')
    tbl.formulaColumn('n_invoices', select=dict(table='invc.invoice', columns='COUNT(*)', where='$customer_id=#THIS.id'), dtype='L', name_long='N.Invoices', group='e_activity.01')
    tbl.formulaColumn('invoiced_total', select=dict(table='invc.invoice', columns='SUM($total)', where='$customer_id=#THIS.id'), dtype='N', name_long='Invoiced Total', group='e_activity.02')
    tbl.formulaColumn('last_invoice_id', select=dict(table='invc.invoice', columns='$id', where='$customer_id=#THIS.id', order_by='$date DESC', limit=1), dtype='T', name_long='Last Invoice', group='e_activity.04').relation('invoice.id', foreign_key=False, relation_name='last_invoice', one_group='e_activity.04')
    tbl.formulaColumn('full_address', sql_formula="$street_address || ', ' || $suburb", dtype='T', name_long='Full Address', group='b_address.05')
    tbl.formulaColumn('has_invoices', exists=dict(table='invc.invoice', where='$customer_id=#THIS.id'), dtype='B', name_long='Has Invoices', group='e_activity.06')
    tbl.formulaColumn('customer_rank', sql_formula="CASE WHEN $n_invoices = 0 THEN 'Inactive' WHEN $n_invoices < 5 THEN 'Occasional' ELSE 'Regular' END", dtype='A', name_long='Customer Rank', group='005')
    tbl.formulaColumn('display_name', sql_formula="COALESCE($account_name, 'Unknown')", dtype='T', name_long='Display Name', group='003')
    tbl.formulaColumn('postcode_padded', sql_formula="LPAD($postcode, 5, '0')", dtype='T', name_long='Postcode Padded', group='b_address.06')
    tbl.aliasColumn('state_name', relation_path='@state.name', name_long='State Name', group='b_address.07')
    tbl.aliasColumn('payment_description', relation_path='@payment_type_code.description', name_long='Payment Description', group='d_billing.02')
    tbl.aliasColumn('region_name', relation_path='@state.@region_code.name', name_long='Region Name', group='b_address.08')
    tbl.formulaColumn('account_code', sql_formula="LPAD(CAST($id AS TEXT), 8, '0')", dtype='T', name_long='Account Code', group='004')
    tbl.formulaColumn('is_active_valuable', sql_formula='$has_invoices AND $n_invoices >= 3', dtype='B', name_long='Active Valuable Customer', group='e_activity.08')
    tbl.formulaColumn('contact_info', sql_formula="CONCAT(COALESCE($email, 'no-email'), ' | ', COALESCE($phone, 'no-phone'))", dtype='T', name_long='Contact Info', group='c_contacts.03')
    tbl.pyColumn('customer_score', dtype='N', required_columns='$account_name,$email', name_long='Customer Score', group='e_activity.09', method='pyColumn_customer_score')
    tbl.formulaColumn('invoice_numbers', sql_formula="array_to_string(ARRAY(#inv_nums), ', ')", select_inv_nums=dict(table='invc.invoice', columns='$inv_number', where='$customer_id=#THIS.id', order_by='$date DESC', limit=5), dtype='T', name_long='Invoice Numbers', group='e_activity.05')
    tbl.formulaColumn('avg_invoice_value', sql_formula='$invoiced_total / NULLIF($n_invoices, 0)', dtype='N', name_long='Avg Invoice Value', group='e_activity.03')
    tbl.formulaColumn('has_activity', sql_formula='$has_invoices OR EXISTS(SELECT 1 FROM invc.invc_invoice_note AS n INNER JOIN invc.invc_invoice AS i ON n.invoice_id = i.id WHERE i.customer_id = #THIS.id)', dtype='B', name_long='Has Activity', group='e_activity.07')
    tbl.formulaColumn('is_confirmed', sql_formula='$__is_draft IS NOT TRUE', dtype='B', name_long='Is Confirmed', group='006')


# projects/test_invoice/packages/invc/model/customer_type.py
# SHA256: 2999028f75bd7f3ce73afbf4fccc8372df69a4aee2ab46836d840a15767cc242
def customer_type(pkg):
    tbl = pkg.table('customer_type', pkey='code', name_long='!!Customer type', name_plural='!!Customer types', caption_field='description', lookup=True)
    tbl.options().sys_fields(id=False, user_upd=False, group_name='!![en]System')
    tbl.column('code', size=':5', name_long='!!Code')
    tbl.column('description', name_long='Description')


# projects/test_invoice/packages/invc/model/discount_tier.py
# SHA256: 4a1f004b5eda312a863d13cc9f019ce9bba82f60fdf747e156eeaf23048c4761
def discount_tier(pkg):
    tbl = pkg.table('discount_tier', pkey='id', name_long='!!Discount Tier', name_plural='!!Discount Tiers')
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.column('customer_type_code', size=':5', name_long='!!Customer Type').relation('customer_type.code', relation_name='discount_tiers', onDelete='cascade', foreign_key=True)
    tbl.column('min_amount', dtype='N', name_long='!!Min Amount')
    tbl.column('max_amount', dtype='N', name_long='!!Max Amount')
    tbl.column('discount_rate', dtype='perc', name_long='!!Discount Rate')
    tbl.column('description', name_long='!!Description')


# projects/test_invoice/packages/invc/model/invoice.py
# SHA256: 71f1ef0b6ad9cc20ddc37383ae08744e94b83fcf4a594204ef11d4947b6fbd8b
def invoice(pkg):
    tbl = pkg.table('invoice', pkey='id', name_long='!!Invoice', name_plural='!!Invoice', caption_field='inv_number',
                    partition_customer_state='invc_state')
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.column('inv_number', size='10', name_long='!!Invoice number', name_short='Inv N', unique=True)
    tbl.column('customer_id', size='22', group='_', name_long='!!Customer').relation('customer.id', relation_name='invoices', onDelete='raise', many_group='z_relations.01', foreign_key=True)
    tbl.column('date', dtype='D', name_long='!!Date', validate_notnull=True)
    tbl.column('total', dtype='money', name_long='!!Total')
    tbl.column('vat_total', dtype='money', name_long='!!VAT total')
    tbl.column('gross_total', dtype='money', name_long='!!Gross total')
    tbl.column('invoice_time', dtype='H', name_long='!!Invoice Time')
    tbl.formulaColumn('row_count', select=dict(table='invc.invoice_row', columns='COUNT(*)', where='$invoice_id=#THIS.id'), dtype='L', name_long='Row Count')
    tbl.formulaColumn('first_product_id', select=dict(table='invc.invoice_row', columns='$product_id', where='$invoice_id=#THIS.id', order_by='$_row_count', limit=1), dtype='T', name_long='First Product').relation('product.id', foreign_key=False, relation_name='first_in_invoice')
    tbl.aliasColumn('customer_name', relation_path='@customer_id.account_name', name_long='Customer Name')
    tbl.aliasColumn('customer_state', relation_path='@customer_id.state', name_long='Customer State')
    tbl.formulaColumn('anno', sql_formula='EXTRACT(YEAR FROM $date)', dtype='T', name_long='Anno')
    tbl.formulaColumn('periodo', sql_formula="TO_CHAR($date,'YYYY-MM')", dtype='A', name_long='Periodo')
    tbl.formulaColumn('value_category', sql_formula="CASE WHEN $total > 1000 THEN 'High' WHEN $total > 100 THEN 'Medium' ELSE 'Low' END", dtype='A', name_long='Value Category')
    tbl.formulaColumn('display_total', sql_formula='COALESCE($gross_total, $total, 0)', dtype='N', name_long='Display Total')
    tbl.virtualRelation('discount_tier_id', table='invc.discount_tier', condition='$customer_type_code = :var_customer_type_code AND $min_amount <= :var_total AND $max_amount > :var_total', var_customer_type_code='@customer_id.customer_type_code', var_total='$total')
    tbl.aliasColumn('discount_tier_id', '@discount_tier_id.id', name_long='Discount Tier')
    tbl.formulaColumn('all_notes', select=dict(table='invc.invoice_note', columns="STRING_AGG($note_text, ' | ' ORDER BY $priority)", where='$invoice_id=#THIS.id'), dtype='T', name_long='All Notes')
    tbl.formulaColumn('priority_note', sql_formula="COALESCE(#top_note, 'No notes')", select_top_note=dict(table='invc.invoice_note', columns='$note_text', where='$invoice_id=#THIS.id', order_by='$priority', limit=1), dtype='T', name_long='Priority Note')
    tbl.formulaColumn('invoice_status', sql_formula="CASE WHEN $total IS NULL THEN 'Draft'\n                                              WHEN $total = 0 THEN 'Empty'\n                                              ELSE CASE WHEN $gross_total > 5000 THEN 'Large'\n                                                        WHEN $gross_total > 1000 THEN 'Medium'\n                                                        ELSE 'Small' END\n                                         END", dtype='A', name_long='Invoice Status')
    tbl.formulaColumn('status_label', sql_formula='CASE WHEN $total > 1000 THEN :high_label\n                                              WHEN $total > 100 THEN :mid_label\n                                              ELSE :low_label END', var_high_label='Premium Invoice', var_mid_label='Standard Invoice', var_low_label='Basic Invoice', dtype='A', name_long='Status Label')
    tbl.formulaColumn('days_since_invoice', sql_formula="date_part('day', now() - $date)", dtype='L', name_long='Days Since Invoice')
    tbl.formulaColumn('number_series', sql_formula="CASE WHEN $inv_number LIKE :pat_a THEN 'Series A'\n                                              WHEN $inv_number LIKE :pat_b THEN 'Series B'\n                                              ELSE 'Other' END", var_pat_a='A%%', var_pat_b='B%%', dtype='A', name_long='Number Series')
    tbl.formulaColumn('week_start', sql_formula="$date - MOD(CAST(EXTRACT(DOW FROM $date) AS integer) + 6, 7) * INTERVAL '1 day'", dtype='D', name_long='Week Start')
    tbl.formulaColumn('priced_rows_pct', select=dict(table='invc.invoice_row', columns='COUNT(*) FILTER (WHERE $unit_price IS NOT NULL) * 100.0 / NULLIF(COUNT(*), 0)', where='$invoice_id=#THIS.id'), dtype='N', name_long='Priced Rows Pct')
    tbl.formulaColumn('invoice_datetime', sql_formula='$date + $invoice_time', dtype='DH', name_long='Invoice Datetime')
    tbl.formulaColumn('invoice_month', sql_formula="date_trunc('month', $date)", dtype='D', name_long='Invoice Month')
    tbl.formulaColumn('smart_row_count', sql_formula='CASE WHEN $total > 1000 THEN #high_rows ELSE #all_rows END', select_high_rows=dict(table='invc.invoice_row', columns='COUNT(*)', where='$invoice_id=#THIS.id AND $unit_price > 100'), select_all_rows=dict(table='invc.invoice_row', columns='COUNT(*)', where='$invoice_id=#THIS.id'), dtype='L', name_long='Smart Row Count')
    tbl.formulaColumn('has_expensive_rows', exists=dict(table='invc.invoice_row', where='$invoice_id=#THIS.id AND $unit_price > 100'), dtype='B', name_long='Has Expensive Rows')
    tbl.formulaColumn('duplicate_products', sql_formula='COALESCE(#dup_prods, 0)', select_dup_prods=dict(table='invc.invoice_row', columns='COUNT(*)', where='$invoice_id=#THIS.id', group_by='$product_id', having='COUNT(*) > 1'), dtype='L', name_long='Duplicate Products')
    tbl.formulaColumn('due_date', sql_formula="$date + INTERVAL '30 days'", dtype='D', name_long='Due Date')
    tbl.formulaColumn('created_same_day', sql_formula='CAST($__ins_ts AS DATE) = $date', dtype='B', name_long='Created Same Day')
    tbl.formulaColumn('is_recent', sql_formula="$date >= :env_workdate - INTERVAL '90 days'", dtype='B', name_long='Is Recent')
    tbl.subQueryColumn('rows_json', query=dict(table='invc.invoice_row', columns='$product_id,$quantity,$unit_price', where='$invoice_id=#THIS.id'), mode='json')
    tbl.subQueryColumn('notes_xml', query=dict(table='invc.invoice_note', columns='$note_type,$note_text', where='$invoice_id=#THIS.id'), mode='xml')
    tbl.subQueryColumn('max_row_price', query=dict(table='invc.invoice_row', columns='MAX($unit_price)', where='$invoice_id=#THIS.id'), dtype='N', name_long='Max Row Price')
    tbl.options().numbering('inv_number', parameters=dict(format='$K$YY/$NNNNNN', code='A', period='YY', date_field='date', showOnLoad=True, recycle=True))


# projects/test_invoice/packages/invc/model/invoice_note.py
# SHA256: fdf3e7d61cb64e9876bbfa273d7f45e5eebff48a0b23374a0ebca3d7550d55c3
def invoice_note(pkg):
    tbl = pkg.table('invoice_note', pkey='id', name_long='!!Invoice Note', name_plural='!!Invoice Notes')
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.column('invoice_id', size='22', group='_', name_long='!!Invoice').relation('invoice.id', relation_name='notes', onDelete='cascade', foreign_key=True)
    tbl.column('note_type', size=':20', name_long='!!Note Type')
    tbl.column('note_text', name_long='!!Note Text')
    tbl.column('priority', dtype='I', name_long='!!Priority')
    tbl.formulaColumn('is_warning', sql_formula='$note_type LIKE :warn_pat', var_warn_pat='WARN%%', dtype='B', name_long='Is Warning')
    tbl.formulaColumn('note_type_clean', sql_formula='UPPER(TRIM($note_type))', dtype='T', name_long='Note Type Clean')
    tbl.formulaColumn('created_date', sql_formula="date_trunc('day', $__ins_ts)", dtype='D', name_long='Created Date')
    tbl.formulaColumn('note_text_rtrim', sql_formula='RTRIM($note_text)', dtype='T', name_long='Note Text Rtrim')


# projects/test_invoice/packages/invc/model/invoice_row.py
# SHA256: efe2006560c1753630a1873a3e33f09c28107c773e9ea82467d6391c355f3dd4
def invoice_row(pkg):
    tbl = pkg.table('invoice_row', pkey='id', name_long='!!Invoice row', name_plural='!!Invoice rows')
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.options().auto_counter('invoice_id')
    tbl.column('invoice_id', size='22', group='_', name_long='!!Invoice').relation('invoice.id', relation_name='rows', onDelete='cascade', foreign_key=True)
    tbl.column('product_id', size='22', group='_', name_long='!!Product').relation('product.id', relation_name='invoice_rows', onDelete='raise', foreign_key=True)
    tbl.column('quantity', dtype='I', name_long=u'!![it]Quantity', name_short='Q.')
    tbl.column('unit_price', dtype='money', name_long='!!Unit price', name_short='U.Pr.')
    tbl.column('tot_price', dtype='money', name_long='!!Total price', name_short='T.Pr.')
    tbl.column('vat', dtype='money', name_long='VAT', name_short='VAT')
    tbl.column('vat_rate', dtype='perc', name_long='!![it]Vat rate')
    tbl.aliasColumn('customer_name', relation_path='@invoice_id.@customer_id.account_name', name_long='Customer name')
    tbl.aliasColumn('customer_id', relation_path='@invoice_id.customer_id', name_long='Customer id')
    tbl.aliasColumn('product_name', relation_path='@product_id.description', name_long='Product Name')
    tbl.aliasColumn('customer_state', relation_path='@invoice_id.@customer_id.@state.name', name_long='Customer State')
    tbl.formulaColumn('line_total', sql_formula='$quantity * $unit_price', dtype='N', name_long='Line Total')
    tbl.formulaColumn('line_vat', sql_formula='$line_total * $vat_rate', dtype='N', name_long='Line VAT')
    tbl.formulaColumn('line_gross', sql_formula='$line_total + $line_vat', dtype='N', name_long='Line Gross')
    tbl.formulaColumn('size_category', sql_formula="CASE WHEN $quantity IN (1,2,3) THEN 'Small' WHEN $quantity < 100 THEN 'Medium' ELSE 'Large' END", dtype='A', name_long='Size Category')
    tbl.formulaColumn('product_note', sql_formula="CASE WHEN @product_id.unit_price > 500 THEN 'Premium' ELSE 'Standard' END", dtype='A', name_long='Product Note')
    tbl.formulaColumn('effective_price', sql_formula='COALESCE($unit_price, @product_id.unit_price)', dtype='money', name_long='Effective Price')
    tbl.formulaColumn('is_expensive', sql_formula='$line_total > 1000', dtype='B', name_long='Is Expensive')
    tbl.formulaColumn('needs_review', sql_formula='$is_expensive OR ($quantity > 50 AND $unit_price < 1)', dtype='B', name_long='Needs Review')
    tbl.formulaColumn('pricing_analysis', sql_formula="CASE WHEN $effective_price IS NULL THEN 'No price'\n                                              WHEN $effective_price > @product_id.unit_price\n                                                   THEN 'Above list'\n                                              WHEN $effective_price < @product_id.unit_price\n                                                   THEN 'Discounted'\n                                              ELSE 'At list price' END", dtype='A', name_long='Pricing Analysis')
    tbl.aliasColumn('customer_region', relation_path='@invoice_id.@customer_id.@state.@region_code.name', name_long='Customer Region')
    tbl.formulaColumn('product_code_prefix', sql_formula='substr(@product_id.code, 1, 3)', dtype='T', name_long='Product Code Prefix')
    tbl.formulaColumn('rounded_total', sql_formula='ROUND($line_total, 2)', dtype='N', name_long='Rounded Total')
    tbl.formulaColumn('abs_discount', sql_formula='ABS($unit_price - @product_id.unit_price)', dtype='N', name_long='Abs Discount')
    tbl.formulaColumn('prev_quantity', sql_formula='LAG($quantity, 1) OVER (PARTITION BY $invoice_id ORDER BY $_row_count)', dtype='I', name_long='Previous Quantity')
    tbl.formulaColumn('matches_list_price', sql_formula='CAST($unit_price = @product_id.unit_price AS boolean)', dtype='B', name_long='Matches List Price')
    tbl.formulaColumn('distinct_products_in_invoice', sql_formula='array_length(ARRAY(SELECT DISTINCT ir.product_id\n                                                            FROM invc.invc_invoice_row AS ir\n                                                            WHERE ir.invoice_id = #THIS.invoice_id), 1)', dtype='L', name_long='Distinct Products In Invoice')
    tbl.formulaColumn('is_exempt_vat', sql_formula='@product_id.vat_type_code IN :exempt_codes', var_exempt_codes=['FRE', 'INP'], dtype='B', name_long='Is Exempt VAT')
    tbl.aliasColumn('invoice_date_static', relation_path='@invoice_id.date', static=True, dtype='D', name_long='Invoice Date Static')
    tbl.virtualRelation('customer', relation='@invoice_id.@customer_id')
    tbl.formulaColumn('adjusted_total', sql_formula='$line_total * #PREF(markup_rate,1)', dtype='N', name_long='Adjusted Total')


# projects/test_invoice/packages/invc/model/payment_type.py
# SHA256: c5672daa4d420802f7088ad9482368b95713915c23a95e61060367785682eaec
def payment_type(pkg):
    tbl = pkg.table('payment_type', pkey='code', name_long='!!Payment type', name_plural='!!Payment types', caption_field='description', lookup=True)
    tbl.options().sys_fields(id=False, user_upd=False, group_name='!![en]System')
    tbl.column('code', size=':10', name_long='!!Code')
    tbl.column('description', name_long='Description')


# projects/test_invoice/packages/invc/model/postcode.py
# SHA256: 100df477a120d6e5cd7a18b3e303b9f0cedc38a4b105416181610c298bf985ef
def postcode(pkg):
    tbl = pkg.table('postcode', name_long='Postcode', name_plural='Postcodes', pkey='id', caption_field='postcode', lookup=False)
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.column('postcode', size=':10', name_long='postcode', unique=False, indexed=True)
    tbl.column('suburb', size=':100', name_long='suburb')
    tbl.column('state', size=':5', name_long='state').relation('state.code', relation_name='postcodes', foreign_key=True)
    tbl.column('lat', name_long='lat')
    tbl.column('lon', name_long='lon')


# projects/test_invoice/packages/invc/model/price_year.py
# SHA256: 48961724f864f130c2c59b42cf50ba684bbb075c67ae990418a10417d0562983
def price_year(pkg):
    tbl = pkg.table('price_year', pkey='id', name_long='!!Price Year', name_plural='!!Price Years')
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.column('product_id', size='22', group='_', name_long='!!Product').relation('product.id', relation_name='price_years', onDelete='cascade', foreign_key=True)
    tbl.column('year', dtype='L', name_long='!!Year')
    tbl.column('unit_price', dtype='money', name_long='!!Unit Price')
    tbl.column('note', name_long='!!Note')
    tbl.compositeColumn('product_year_key', columns='product_id,year', unique=True)
    tbl.formulaColumn('price_label', sql_formula="CAST($year AS TEXT) || ': ' || CAST($unit_price AS TEXT)", dtype='T', name_long='Price Label')
    tbl.aliasColumn('product_description', relation_path='@product_id.description', name_long='Product Description')


# projects/test_invoice/packages/invc/model/price_year_note.py
# SHA256: e22bea4fdfce53faf64d1974ad8a3fc826ca613e8c156d1c6804277d3dc7e49f
def price_year_note(pkg):
    tbl = pkg.table('price_year_note', pkey='id', name_long='!!Price Year Note', name_plural='!!Price Year Notes')
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.column('product_id', size='22', group='_', name_long='!!Product').relation('product.id', relation_name='price_year_notes', onDelete='cascade', foreign_key=True)
    tbl.column('year', dtype='L', name_long='!!Year')
    tbl.compositeColumn('product_year_ref', columns='product_id,year').relation('price_year.product_year_key', foreign_key=False, relation_name='notes')
    tbl.column('note_text', name_long='!!Note Text')
    tbl.column('importance', dtype='I', name_long='!!Importance')
    tbl.aliasColumn('price_year_price', relation_path='@product_year_ref.unit_price', name_long='Price Year Price')
    tbl.aliasColumn('price_year_label', relation_path='@product_year_ref.price_label', name_long='Price Year Label')
    tbl.aliasColumn('product_description', relation_path='@product_year_ref.@product_id.description', name_long='Product Description')


# projects/test_invoice/packages/invc/model/product.py
# SHA256: 2225c75ce1cf8fca62c46d8db7b6a3ce0b7ae72c38a71b24919e04382bf767b8
def product(pkg):
    tbl = pkg.table('product', pkey='id', name_long='!!Product', name_plural='!!Prodocts', caption_field='description')
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.column('code', size=':10', name_long='!!Code')
    tbl.column('description', size=':80', name_long='!!Description')
    tbl.column('presentation_txt', name_long='!!Presentation')
    tbl.column('vat_type_code', size=':5', group='_', name_long='!![it]VAT type').relation('vat_type.code', relation_name='products', onDelete='raise', foreign_key=True)
    tbl.column('product_type_id', size='22', group='_', name_long='!!Product type', name_short='Type').relation('product_type.id', relation_name='products', onDelete='raise', foreign_key=True)
    tbl.column('unit_price', dtype='money', name_long='!!Price', name_short='Price')
    tbl.column('image_url', dtype='P', name_long='!!Image url', name_short='Img')
    tbl.column('details', dtype='X', name_long='!!Details')
    tbl.column('details').dynamic_fields(source='product_type_id')
    tbl.formulaColumn('picture', 'image_url', dtype='P', name_long='!!Picture', name_short='Img')
    tbl.formulaColumn('total_sold', select=dict(table='invc.invoice_row', columns='SUM($quantity)', where='$product_id=#THIS.id'), dtype='N', name_long='Total Sold')
    tbl.formulaColumn('price_range', sql_formula="CASE WHEN $unit_price > 500 THEN 'Premium' WHEN $unit_price > 100 THEN 'Mid' ELSE 'Budget' END", dtype='A', name_long='Price Range')
    tbl.formulaColumn('code_and_desc', sql_formula="$code || ' - ' || $description", dtype='T', name_long='Code and Description')
    tbl.formulaColumn('price_floor', sql_formula='GREATEST($unit_price, 10)', dtype='money', name_long='Price Floor')
    tbl.formulaColumn('price_label', sql_formula="$description || ' (' || CAST($unit_price AS TEXT) || ')'", dtype='T', name_long='Price Label')
    tbl.aliasColumn('product_type_name', relation_path='@product_type_id.description', name_long='Product Type')
    tbl.bagItemColumn('detail_weight', bagcolumn='$details', itempath='specs.weight', dtype='N', name_long='Detail Weight')
    tbl.bagItemColumn('detail_color', bagcolumn='$details', itempath='specs.color', dtype='T', name_long='Detail Color')
    tbl.bagItemColumn('detail_price', bagcolumn='$details', itempath='specs.price', dtype='money', name_long='Detail Price')
    tbl.formulaColumn('concat_code_desc', sql_formula="CONCAT($code, ' - ', $description)", dtype='T', name_long='Concat Code Desc')
    tbl.formulaColumn('code_normalized', sql_formula="lower(regexp_replace($code, '[^a-zA-Z0-9]', '', 'g'))", dtype='T', name_long='Code Normalized')
    tbl.formulaColumn('code_clean', sql_formula="translate($code, ' /-', '___')", dtype='T', name_long='Code Clean')
    tbl.pyColumn('computed_margin', dtype='N', required_columns='$unit_price', name_long='Computed Margin', method='pyColumn_computed_margin')
    tbl.formulaColumn('price_rounded', sql_formula='ROUND($unit_price, 0)', dtype='N', name_long='Price Rounded')
    tbl.formulaColumn('description_clean', sql_formula="REPLACE($description, ' ', '-')", dtype='T', name_long='Description Clean')
    tbl.formulaColumn('code_prefix_std', sql_formula='substring($code FROM 1 FOR 3)', dtype='T', name_long='Code Prefix Std')
    tbl.formulaColumn('price_as_int_text', sql_formula='CAST(CAST($unit_price AS integer) AS text)', dtype='T', name_long='Price As Int Text')


# projects/test_invoice/packages/invc/model/product_group.py
# SHA256: 843362e819ea035948036f0e4a441fed905998fc60c9693824beec19585fed41
def product_group(pkg):
    tbl = pkg.table('product_group', pkey='id', name_long='!!Product group', name_plural='!!Product groups', caption_field='hierarchical_code')
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.options().hierarchical('code,_row_count')
    tbl.options().auto_counter()
    tbl.column('code', size=':10', name_long='!!Code')
    tbl.column('description', size=':50', name_long='!!Description')


# projects/test_invoice/packages/invc/model/product_type.py
# SHA256: f8a6bc9a38bd27e366a60e3c14367092eb47e15cf119aa280fd64a410916ba0f
def product_type(pkg):
    tbl = pkg.table('product_type', pkey='id', name_long='!!Product type', name_plural='!!Product types', caption_field='hierarchical_description')
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.options().hierarchical('description')
    tbl.options().auto_counter()
    tbl.options().dynamic_fields()
    tbl.column('description', size=':50', name_long='!!Description')


# projects/test_invoice/packages/invc/model/region.py
# SHA256: 3ad7ed5b7a0e9b00b9bfec034de6b6ac0f79f2c0d4f99ecd00bd6e87e324339d
def region(pkg):
    tbl = pkg.table('region', pkey='code', name_long='!!Region', name_plural='!!Regions')
    tbl.options().sys_fields(id=False, user_upd=False, group_name='!![en]System')
    tbl.column('code', size=':5', name_long='!!Code')
    tbl.column('name', size=':50', name_long='!!Name')


# projects/test_invoice/packages/invc/model/staff.py
# SHA256: 4d315c52b346ce233df251ec2f7db514f01dd4e303698cbbd3b31a273e7f08b9
def staff(pkg):
    tbl = pkg.table('staff', pkey='id', name_long='!!Staff', name_plural='!!Staff Members', caption_field='full_name')
    tbl.options().sys_fields(user_upd=False, group_name='!![en]System')
    tbl.column('first_name', name_long='!!First Name', validate_notnull=True)
    tbl.column('last_name', name_long='!!Last Name', validate_notnull=True)
    tbl.column('email', name_long='!!Email')
    tbl.column('hire_date', dtype='D', name_long='!!Hire Date')
    tbl.column('state', size=':5', name_long='!!State').relation('invc.state.code', relation_name='staff_members', onDelete='raise', foreign_key=True)
    tbl.column('role_code', size=':5', name_long='!!Role').relation('staff_role.code', relation_name='staff_members', onDelete='raise', foreign_key=True)
    tbl.column('user_id', size='22', name_long='!!User').relation('adm.user.id', relation_name='staff_member', onDelete='setnull', foreign_key=True)
    tbl.formulaColumn('full_name', sql_formula="$first_name || ' ' || $last_name", dtype='T', name_long='Full Name')
    tbl.aliasColumn('state_name', relation_path='@state.name', name_long='State Name')
    tbl.aliasColumn('role_description', relation_path='@role_code.description', name_long='Role Description')
    tbl.aliasColumn('region_name', relation_path='@state.@region_code.name', name_long='Region Name')
    tbl.aliasColumn('username', relation_path='@user_id.username', name_long='Username')


# projects/test_invoice/packages/invc/model/staff_role.py
# SHA256: a5b8935b7f165eeddf85d12dd8ecce432e26308b2926fdcbe9560dcabfe2286e
def staff_role(pkg):
    tbl = pkg.table('staff_role', pkey='code', name_long='!!Staff Role', name_plural='!!Staff Roles', caption_field='description', lookup=True)
    tbl.options().sys_fields(id=False, user_upd=False, group_name='!![en]System')
    tbl.column('code', size=':5', name_long='!!Code')
    tbl.column('description', name_long='!!Description')


# projects/test_invoice/packages/invc/model/state.py
# SHA256: 4a85671eba7775a08dbdcba977aed888ea602584ea2184db1e17c5c1e87aa97a
def state(pkg):
    tbl = pkg.table('state', pkey='code', name_long='!!State', name_plural='!!States', caption_field='code', lookup=True)
    tbl.options().sys_fields(id=False, user_upd=False, group_name='!![en]System')
    tbl.column('code', size=':5', name_long='!!Code')
    tbl.column('name', size=':100', name_long='!!Name')
    tbl.column('region_code', size=':5', name_long='!!Region').relation('region.code', relation_name='states', onDelete='raise', foreign_key=True)


# projects/test_invoice/packages/invc/model/vat_type.py
# SHA256: c67510e283501730f02c50a65a80c68fd6a8c4b97c472b04f260f820c8c73a80
def vat_type(pkg):
    tbl = pkg.table('vat_type', pkey='code', name_long='!!VAT type', name_plural='!!VAT types', caption_field='description', lookup=True)
    tbl.options().sys_fields(id=False, user_upd=False, group_name='!![en]System')
    tbl.column('code', size=':5', name_long='!!Code')
    tbl.column('description', name_long='Description')
    tbl.column('vat_rate', dtype='perc', name_long='!!VAT rate')


def configure(pkg):
    customer(pkg)
    customer_type(pkg)
    discount_tier(pkg)
    invoice(pkg)
    invoice_note(pkg)
    invoice_row(pkg)
    payment_type(pkg)
    postcode(pkg)
    price_year(pkg)
    price_year_note(pkg)
    product(pkg)
    product_group(pkg)
    product_type(pkg)
    region(pkg)
    staff(pkg)
    staff_role(pkg)
    state(pkg)
    vat_type(pkg)
