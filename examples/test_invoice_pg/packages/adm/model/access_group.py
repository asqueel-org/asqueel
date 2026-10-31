# projects/gnrcore/packages/adm/model/access_group.py
# SHA256: e2bcddd3ce1b79cfade1e83b8d365c81adfb2cf325abcd8d0b9da83d22ce2811


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('access_group', pkey='code', name_long='!!Access group', name_plural='!!Access group', caption_field='code')
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.column('code', size=':10', name_long='!!Code')
        tbl.column('description', size=':30', name_long='!!Description')
        tbl.column('allowed_ip', name_long='!!Allowed ip')
