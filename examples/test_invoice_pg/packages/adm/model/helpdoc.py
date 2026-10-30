# projects/gnrcore/packages/adm/model/helpdoc.py
# SHA256: 7f362f8b23a22928a3cedb9d469bb370ca88d64caaeca1c45da10759fc0a810e


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('helpdoc', pkey='id', name_long='!![en]Help document', name_plural='!![en]Help documents', caption_field='title', lookup=True)
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('title', size=':25', name_long='Title')
        tbl.column('url', name_long='Url')
        tbl.column('description', name_long='Description')
