# projects/gnrcore/packages/adm/model/group_helpdoc.py
# SHA256: a27d57f7946d10830b47b418919836e72d60a76994522addeec2f29dee32aee5


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('group_helpdoc', pkey='id', name_long='!![en]Help document for group', name_plural='!![en]Help documents for group', caption_field='')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.options().counter('group_code')
        tbl.column('group_code', size=':15', group='_', name_long='Group').relation('group.code', relation_name='helpdocs', onDelete='raise', foreign_key=True)
        tbl.column('helpdoc_id', size='22', group='_', name_long='Help document').relation('helpdoc.id', relation_name='connected_groups', onDelete='cascade', foreign_key=True)
        tbl.aliasColumn('url', '@helpdoc_id.url', name_long='Url', static=True)
