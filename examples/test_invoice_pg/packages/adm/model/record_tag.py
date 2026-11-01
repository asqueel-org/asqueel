# projects/gnrcore/packages/adm/model/record_tag.py
# SHA256: 06c231ecc1dc94753ece00060d0bf48934346331da8171ebe0d120eec74abf6c


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('record_tag', pkey='id', name_long='!!Table tag', name_plural='!!Table tags')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('tablename', name_long='!!Table name')
        tbl.column('tag', name_long='!!Tag')
        tbl.column('description', name_long='!!Description')
