# projects/gnrcore/packages/sys/model/dataretention.py
# SHA256: 6b9d8a9b05916c5f044ebf173490411ba71316e0cccb28c2b2a66bdbc5334c6d


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('dataretention', rowcaption='$table_fullname', caption_field='task_fullname', pkey='id', name_long='!!Data Retention Policy', name_plural='!!Data Retention Policies')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('table_fullname', name_long='!!Table', unique=True)
        tbl.column('filter_column', name_long='!!Filter Column')
        tbl.column('retention_period', dtype='L', name_long='!!Retention (days)')
