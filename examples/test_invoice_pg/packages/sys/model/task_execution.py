# projects/gnrcore/packages/sys/model/task_execution.py
# SHA256: 9f3279b30413ddb7004f887bfe32618d78ec25a2774657e4bf7241000031cda5


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('task_execution', pkey='id', name_long='!!Task execution', name_plural='!!Task executions')
        tbl.options().retention(field='__ins_ts', days=180)
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('task_id', size='22', name_long='!!Task ID').relation('sys.task.id', relation_name='executions', onDelete='cascade', foreign_key=True)
        tbl.column('result', 'X', name_long='!!result')
        tbl.column('logbag', 'X', name_long='!!Logbag')
        tbl.column('errorbag', 'X', name_long='!!Errors')
        tbl.column('pid', dtype='L', name_long='!!Process id', name_short='!!PID')
        tbl.column('start_ts', dtype='DH', name_long='!!Start Time', indexed=True)
        tbl.column('end_ts', dtype='DH', name_long='!!End Time', indexed=True)
        tbl.column('is_error', 'B', name_long='!!Is Error', indexed=True)
        tbl.column('exec_reason', size=':20', name_long='!!Exec reason')
        tbl.column('reasonkey', size=':60', indexed=True)
        tbl.aliasColumn('task_table', '@task_id.table_name', name_long='!!Table')
        tbl.aliasColumn('task_name', '@task_id.task_name', name_long='!!Task name', name_short='!!Name')
        tbl.aliasColumn('task_command', '@task_id.command', name_long='!!Task command', name_short='!!Command')
        tbl.aliasColumn('task_stopped', '@task_id.stopped', dtype='B', name_long='!!Stopped')
        tbl.aliasColumn('task_parameters', '@task_id.parameters', dtype='X', name_long='!!Parameters')
        tbl.aliasColumn('task_saved_query', '@task_id.saved_query_code', dtype='B', name_long='!!Saved query')
        tbl.aliasColumn('task_worker_code', '@task_id.worker_code', dtype='L', name_long='!!Task worker code')
        tbl.aliasColumn('task_max_workers', '@task_id.max_workers', dtype='L', name_long='!!Task Max workers')
        tbl.aliasColumn('task_active_workers', '@task_id.active_workers', dtype='L', name_long='!!Task Active workers')
        tbl.formulaColumn('status', "\n            (CASE WHEN $is_error IS TRUE THEN 'error'\n                 WHEN $end_ts IS NOT NULL THEN 'completed'\n                 WHEN $start_ts IS NOT NULL THEN 'running'\n                 ELSE 'waiting'\n            END)\n        ", name_long='Status', dtype='A')
