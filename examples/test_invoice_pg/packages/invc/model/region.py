# projects/test_invoice/packages/invc/model/region.py
# SHA256: 3ad7ed5b7a0e9b00b9bfec034de6b6ac0f79f2c0d4f99ecd00bd6e87e324339d


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('region', pkey='code', name_long='!!Region', name_plural='!!Regions')
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.column('code', size=':5', name_long='!!Code')
        tbl.column('name', size=':50', name_long='!!Name')
