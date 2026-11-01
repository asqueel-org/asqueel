# projects/gnrcore/packages/sys/model/task_result.py
# SHA256: fbc99a46858ca9f82cba2dfef8044b33f0fbc2893f220f656fc6fac51439ab60


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('task_result', pkey='id', name_long='!!Task log')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('task_id', size='22', name_long='!!Task ID').relation('sys.task.id', relation_name='logs', foreign_key=True)
        tbl.column('result', 'X', name_long='!!result')
        tbl.column('result_time', dtype='DH', name_long='!!Result Time')
        tbl.column('start_time', dtype='DH', name_long='!!Start Time')
        tbl.column('end_time', dtype='DH', name_long='!!Start Time')
        tbl.column('is_error', 'B', name_long='!!Is Error')
