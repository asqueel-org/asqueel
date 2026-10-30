# projects/gnrcore/packages/adm/model/_packages/sys/task.py
# SHA256: 40abd0b1f867381eb96213aaa8444ee770fecc378014a24bc148685d928e4fc9


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('task')
        tbl.column('user_id').relation('adm.user.id', onDelete='raise', foreign_key=True)
