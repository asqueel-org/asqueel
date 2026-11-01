# projects/gnrcore/packages/adm/model/served_page.py
# SHA256: 863a47ed32e3331267bb05444af93faa090348da282ec17c6ec14110c5c09761


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('served_page', pkey='page_id', name_long='!!Served page', name_plural='!!Served pages')
        tbl.options().enabled_when(preference='adm.dev.connection_log_enabled')
        tbl.column('page_id', size='22', name_long='!!Page id')
        tbl.column('pagename', name_long='!!Page name')
        tbl.column('connection_id', size='22', group='_').relation('connection.id', relation_name='pages', onDelete='cascade', foreign_key=True)
        tbl.column('start_ts', 'DH', name_long='!!Start ts')
        tbl.column('end_ts', 'DH', name_long='!!End ts')
        tbl.column('end_reason', size=':12', name_long='!!End Reason')
