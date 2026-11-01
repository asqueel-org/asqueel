# projects/test_invoice/packages/invc/model/customer_type.py
# SHA256: 2999028f75bd7f3ce73afbf4fccc8372df69a4aee2ab46836d840a15767cc242


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('customer_type', pkey='code', name_long='!!Customer type', name_plural='!!Customer types', caption_field='description', lookup=True)
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.column('code', size=':5', name_long='!!Code')
        tbl.column('description', name_long='Description')
