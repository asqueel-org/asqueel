# projects/gnrcore/packages/adm/model/connection.py
# SHA256: 25922e6b4bcbf3572306f958aad3c16e73cf77c2f1ba242feb0b4a449065d08f


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('connection', pkey='id', name_long='!!Connection', name_plural='!!Connections')
        tbl.options().enabled_when(preference='adm.dev.connection_log_enabled')
        tbl.column('id', size='22', name_long='!!Connection id')
        tbl.column('userid', size='22', name_long='!!Userid').relation('user.id', foreign_key=False)
        tbl.column('username', size=':32', name_long='!!Username')
        tbl.column('ip', size=':255', name_long='!!Ip address')
        tbl.column('start_ts', 'DH', name_long='!!Start TS')
        tbl.column('end_ts', 'DH', name_long='!!End TS')
        tbl.column('end_reason', size=':12', name_long='!!End reason')
        tbl.column('user_agent', name_long='!!User agent')
        tbl.aliasColumn('user_fullname', relation_path='@userid.fullname', name_long='!!User fullname')
