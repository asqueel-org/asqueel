# projects/gnrcore/packages/adm/model/language.py
# SHA256: dc068abbcdb347fc06b21606c7396c4f730fd8a8ba4ae859f2fc103c8eab70e4


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('language', pkey='code', name_long='Language', name_plural='!!Languages', lookup=True, caption_field='name')
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System', syscode=True)
        tbl.options().counter()
        tbl.column('code', size=':2', name_long='!!Code')
        tbl.column('name', name_long='!!Name')
