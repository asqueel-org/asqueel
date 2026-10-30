# projects/test_invoice/packages/invc/model/payment_type.py
# SHA256: c5672daa4d420802f7088ad9482368b95713915c23a95e61060367785682eaec


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('payment_type', pkey='code', name_long='!!Payment type', name_plural='!!Payment types', caption_field='description', lookup=True)
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.column('code', size=':10', name_long='!!Code')
        tbl.column('description', name_long='Description')
