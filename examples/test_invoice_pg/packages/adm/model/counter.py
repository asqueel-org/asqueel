# projects/gnrcore/packages/adm/model/counter.py
# SHA256: 543fa4c606a978c6befb783874c7de0b3318b0e04a958e94787cce92398e5332


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('counter', pkey='codekey', pkey_columns='pkg,tbl,code,fld,period', name_long='!!Counter')
        tbl.options().sysFields(id=False, ins=True, upd=True, user_upd=False, group_name='!![en]System')
        tbl.column('codekey', size=':80', readOnly=True, name_long='!!Codekey', indexed=True)
        tbl.column('code', size=':12', readOnly=True, name_long='!!Code')
        tbl.column('pkg', size=':12', readOnly=True, name_long='!!Package')
        tbl.column('tbl', size=':30', readOnly=True, name_long='!!Table')
        tbl.column('fld', size=':30', readOnly=True, name_long='!!Counter Field')
        tbl.column('period', size=':10', name_long='!!Period', indexed=True)
        tbl.column('counter', 'L', name_long='!!Counter')
        tbl.column('last_used', 'D', name_long='!!Last used')
        tbl.column('holes', 'X', name_long='!!Holes')
        tbl.column('errors', 'X', name_long='!!Errors')
