# projects/test_invoice/packages/invc/model/vat_type.py
# SHA256: c67510e283501730f02c50a65a80c68fd6a8c4b97c472b04f260f820c8c73a80


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('vat_type', pkey='code', name_long='!!VAT type', name_plural='!!VAT types', caption_field='description', lookup=True)
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.column('code', size=':5', name_long='!!Code')
        tbl.column('description', name_long='Description')
        tbl.column('vat_rate', dtype='perc', name_long='!!VAT rate')
