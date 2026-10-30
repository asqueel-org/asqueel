# projects/gnrcore/packages/sys/model/batch_log.py
# SHA256: b43c0a8faa957b3ccf64ae0e311b9c1c76d0e9f079bdc88b84ba928d7438ea16


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('batch_log', pkey='id', name_long='!!Batch log', name_plural='!!Batch logs', caption_field='log_caption')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('batch_title', name_long='!!Batch title')
        tbl.column('page_id', size='22', group='_', name_long='!!Page').relation('adm.served_page.page_id', foreign_key=False, relation_name='batches', onDelete='raise')
        tbl.column('start_ts', dtype='DH', name_long='!!Start ts')
        tbl.column('end_ts', dtype='DH', name_long='!!End ts')
        tbl.column('notes', name_long='!!Notes')
        tbl.column('logbag', dtype='X', name_long='!!Log')
        tbl.column('tbl', name_long='!!Table')
        tbl.formulaColumn('log_caption', '$tbl || $batch_title', dtype='A')
        tbl.formulaColumn('logfile_url', "'/_site/batch_log/'||$id||'.log'", name_long='Log url', dtype='A')
