# projects/gnrcore/packages/adm/model/pkginfo.py
# SHA256: 0e081ed451e78bafb6150236e41b1827c62b0b07be44a0b534a3277e4e3750b1


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('pkginfo', pkey='pkgid', name_long='!!Package info', name_plural='!!Package info', caption_field='pkgid')
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.column('pkgid', size=':50', name_long='!!Package')
        tbl.column('prj', size=':50', name_long='!!Project')
