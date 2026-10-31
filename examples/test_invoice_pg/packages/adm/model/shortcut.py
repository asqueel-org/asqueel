# projects/gnrcore/packages/adm/model/shortcut.py
# SHA256: e48adcb5c48f9ba211f01559ec6f4eb8eb51b40d275b9de17e52df6b4a8b77e8


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('shortcut', pkey='keycode', name_long='!!Shortcut', name_plural='!!Shortcuts', caption_field='phrase', lookup=True)
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.options().counter()
        tbl.column('keycode', size=':10', name_long='!!Key')
        tbl.column('phrase', name_long='!!Phrase')
        tbl.column('groupcode', size=':20', name_long='!!Group')
