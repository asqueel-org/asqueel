# projects/gnrcore/packages/sys/model/widget.py
# SHA256: f0fa9b6419021899fadc943dbf25d65d974b4290df8f55d453f0d7d79b2e883c


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('widget', pkey='id', name_long='!!Widget', name_plural='!!Widgets', caption_field='name')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.options().hierarchical('name')
        tbl.options().df()
        tbl.column('__version', dtype='L', group='zzz', name_long='Audit version')
        tbl.column('name', name_long='!!Name')
        tbl.column('summary', name_long='!!Summary')
        tbl.column('server', dtype='B', name_long='!!Server')
