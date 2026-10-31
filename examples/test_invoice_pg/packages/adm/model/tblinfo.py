# projects/gnrcore/packages/adm/model/tblinfo.py
# SHA256: 62441dab50c549d424819c6ff518f4b0e515113b7dfd7800b48000e8636e0384


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('tblinfo', pkey='tblid', name_long='!!Table Info', name_plural='!!Table info')
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.column('tblid', size=':50', name_long='!!Table')
        tbl.column('pkgid', size=':50', name_long='!!Package').relation('pkginfo.pkgid', foreign_key=False, relation_name='tables')
        tbl.column('description', size=':50', name_long='!!Description')
