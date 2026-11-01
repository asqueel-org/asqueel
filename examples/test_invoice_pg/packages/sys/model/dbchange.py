# projects/gnrcore/packages/sys/model/dbchange.py
# SHA256: 50f5672d7a29b924bf12ccfc1543f1241cbf4db65d8d72e04f81483fc9735677


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('dbchange', pkey='ref', name_long='!!Dbchange', name_plural='!!Db change')
        tbl.options().sysFields(id=False, ins=True, upd=False, ldel=False, user_upd=False, group_name='!![en]System')
        tbl.column('ref', dtype='serial', name_long='!!Reference')
        tbl.column('tbl', size=':80', name_long='!!Table')
        tbl.column('record_pkey', name_long='!!Record pkey')
        tbl.column('evt', size='1', name_long='Evt', name_short='!!Evt')
        tbl.column('record', dtype='X', name_long='!!Record')
        tbl.column('dbstore', size=':60', name_long='!!Dbstore')
