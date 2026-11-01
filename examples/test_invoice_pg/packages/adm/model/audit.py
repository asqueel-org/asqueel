# projects/gnrcore/packages/adm/model/audit.py
# SHA256: c8ce9d0bbf37f451955a3ec9cfa76164ff3f97c4b242413f59c5cee6608fe11c


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('audit', pkey='id', name_long='!!Audit', name_plural='!!Audit')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('tablename', name_long='!!Table name')
        tbl.column('event', size='1', name_long='!!Change type', validate_values='I:Insert,U:Update,D:Delete')
        tbl.column('username', name_long='!!User')
        tbl.column('record_pkey', name_long='!!Record Pkey')
        tbl.column('version', 'L', name_long='!!Version')
        tbl.column('data', 'X', name_long='!!Data')
        tbl.column('transaction_id', name_long='!!Transaction id')
