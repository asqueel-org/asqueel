# projects/gnrcore/packages/adm/model/xgroup.py
# SHA256: c5ba506d4c3486cff97fe321055d804e4eb2f650c69107e98fada791914df6f6


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('xgroup', pkey='code', name_long='!!Deployment group', name_plural='!!Deployment groups', caption_field='description', lookup=True)
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System', syscode=True)
        tbl.column('code', size=':10', name_long='!!Code')
        tbl.column('description', name_long='!!Description')
