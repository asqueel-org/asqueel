# projects/gnrcore/packages/adm/model/user_group.py
# SHA256: c8c825ed64cbc76705d00b754221e272ebd1a19a6dca1d7b62e26bb1c7fe3e23


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('user_group', pkey='id', name_long='!![en]User groups', name_plural='!![en]User groups')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('user_id', size='22', group='_', name_long='User').relation('user.id', relation_name='extra_groups', onDelete='cascade', foreign_key=True)
        tbl.column('group_code', size=':15', group='_', name_long='Group').relation('group.code', relation_name='user_groups', onDelete='cascade', foreign_key=True)
