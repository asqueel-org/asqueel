# projects/test_invoice/packages/invc/model/discount_tier.py
# SHA256: 4a1f004b5eda312a863d13cc9f019ce9bba82f60fdf747e156eeaf23048c4761


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('discount_tier', pkey='id', name_long='!!Discount Tier', name_plural='!!Discount Tiers')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('customer_type_code', size=':5', name_long='!!Customer Type').relation('customer_type.code', relation_name='discount_tiers', onDelete='cascade', foreign_key=True)
        tbl.column('min_amount', dtype='N', name_long='!!Min Amount')
        tbl.column('max_amount', dtype='N', name_long='!!Max Amount')
        tbl.column('discount_rate', dtype='perc', name_long='!!Discount Rate')
        tbl.column('description', name_long='!!Description')
