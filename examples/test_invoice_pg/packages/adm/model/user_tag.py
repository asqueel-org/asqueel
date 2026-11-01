# projects/gnrcore/packages/adm/model/user_tag.py
# SHA256: 48f17ae76da82d6f6be003583c5b82eecbc718991d0ebd2682a70019c35c57fd


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('user_tag', pkey='id', name_long='!!User tag', name_plural='!!User tags')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('group_code', size=':15', name_long='!!Group').relation('group.code', relation_name='tags', onDelete='cascade', foreign_key=True)
        tbl.column('user_id', size='22', group='_', name_long='!!User').relation('user.id', onDelete='cascade', relation_name='tags', foreign_key=True)
        tbl.column('tag_id', size='22', group='_', name_long='!!Tag').relation('htag.id', onDelete='cascade', relation_name='users', foreign_key=True)
        tbl.aliasColumn('user', relation_path='@user_id.username')
        tbl.aliasColumn('fullname', relation_path='@user_id.fullname')
        tbl.aliasColumn('email', relation_path='@user_id.email')
        tbl.aliasColumn('tag_description', relation_path='@tag_id.description')
        tbl.aliasColumn('tag_note', relation_path='@tag_id.note')
        tbl.aliasColumn('linked_table', relation_path='@tag_id.linked_table', static=True)
        tbl.aliasColumn('require_2fa', '@tag_id.require_2fa')
        tbl.aliasColumn('tag_code', '@tag_id.authorization_tag')
        tbl.formulaColumn('user_or_group', 'COALESCE($user,$group_code)', dtype='A')
