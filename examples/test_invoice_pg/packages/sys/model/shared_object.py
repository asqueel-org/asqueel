# projects/gnrcore/packages/sys/model/shared_object.py
# SHA256: c496cdb230492554ac815160eb5a07a007c045e5cced3322131a111c4025d156


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('shared_object', pkey='id', name_long='!!Shared Object', name_plural='Shared objects')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('data', 'X', name_long='!!Data')
        tbl.column('backup', 'X', name_long='!!Backup')
        tbl.column('description', size=':50', name_long='Code', indexed=True)
        tbl.column('linked_table', name_long='!!Table')
