# projects/gnrcore/packages/sys/model/external_token.py
# SHA256: b165f8942cca0ed7974ddeac1692eef024aeba54415611b93e7cdee251d4ce9d


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('external_token', pkey='id', name_long='!!External Token', name_plural='!!External Tokens')
        tbl.column('id', size='22', name_long='!!id')
        tbl.column('datetime', 'DHZ', name_long='!!Date and Time')
        tbl.column('expiry', 'DHZ', name_long='!!Expiry')
        tbl.column('allowed_user', size=':32', name_long='!!Destination user')
        tbl.column('connection_id', size='22', name_long='!!Connection Id', indexed=True).relation('adm.connection.id', foreign_key=False)
        tbl.column('max_usages', 'I', name_long='!!Max uses')
        tbl.column('allowed_host', name_long='!!Allowed host')
        tbl.column('page_path', name_long='!!Page path')
        tbl.column('method', name_long='!!Method')
        tbl.column('assigned_user_id', size='22', group='_', name_long='Assigned user id').relation('adm.user.id', foreign_key=False, relation_name='assigned_tokens', onDelete='cascade')
        tbl.column('parameters', dtype='X', name_long='!!Parameters')
        tbl.column('exec_user', size=':32', name_long='!!Execute as user').relation('adm.user.username', foreign_key=False)
        tbl.column('userobject_id', size='22', group='_', name_long='Userobject').relation('adm.userobject.id', relation_name='tokens', onDelete='cascade', foreign_key=True)
        tbl.pyColumn('external_url', method='pyColumn_external_url')
