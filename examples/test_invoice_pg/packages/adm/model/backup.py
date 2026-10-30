# projects/gnrcore/packages/adm/model/backup.py
# SHA256: 0d32c160befdec3f83a27ae4782e3ac278fdc071a14023441053bc54e40fcc77


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('backup', pkey='id', name_long='!!Backup', name_plural='!!Backups', rowcaption='$name')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('name', name_long='!!Name')
        tbl.column('start_ts', dtype='DH', name_long='!!Backup start ts')
        tbl.column('end_ts', dtype='DH', name_long='!!Backup end ts')
        tbl.column('file_url', name_long='!!Download')
        tbl.formulaColumn('completed', '$end_ts IS NOT NULL', name_long='!!Completed', dtype='A')
