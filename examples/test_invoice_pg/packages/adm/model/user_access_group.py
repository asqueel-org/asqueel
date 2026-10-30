# projects/gnrcore/packages/adm/model/user_access_group.py
# SHA256: f321b5e6ba1ee55589dc612fd0ce37f15d792984308978239346dfd44ce88620


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('user_access_group', pkey='id', name_long='!!User access', name_plural='!!User access')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('user_id', size='22', group='_', name_long='!!User').relation('user.id', relation_name='access_groups', onDelete='cascade', foreign_key=True)
        tbl.column('access_group_code', size=':10', group='_', name_long='!!Access group').relation('access_group.code', relation_name='access_users', onDelete='cascade', foreign_key=True)
