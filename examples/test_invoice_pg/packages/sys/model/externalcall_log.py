# projects/gnrcore/packages/sys/model/externalcall_log.py
# SHA256: 9155945c68e4a2ecdc77a451aeab360a8b799928f3fb86cb52bf3656de98e6e2


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('externalcall_log', pkey='id', name_long='External call log', name_plural='External call log', caption_field='methodname')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('endpoint', name_long='Endpoint')
        tbl.column('methodname', name_long='Method')
        tbl.column('parameters', dtype='X', name_long='Parameters')
        tbl.column('error', name_long='Error')
        tbl.column('result', dtype='X', name_long='Result')
