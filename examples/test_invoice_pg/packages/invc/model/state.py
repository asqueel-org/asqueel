# projects/test_invoice/packages/invc/model/state.py
# SHA256: 4a85671eba7775a08dbdcba977aed888ea602584ea2184db1e17c5c1e87aa97a


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('state', pkey='code', name_long='!!State', name_plural='!!States', caption_field='code', lookup=True)
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.column('code', size=':5', name_long='!!Code')
        tbl.column('name', size=':100', name_long='!!Name')
        tbl.column('region_code', size=':5', name_long='!!Region').relation('region.code', relation_name='states', onDelete='raise', foreign_key=True)
