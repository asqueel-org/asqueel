# projects/gnrcore/packages/adm/model/install_checklist.py
# SHA256: 20ed0176b4a46a0ae2d9d5a364bc0845d45beae0898ad1c33472b02362fbf813


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('install_checklist', pkey='__syscode', name_long='!!Install checklist', name_plural='!!Install checklist', caption_field='description')
        tbl.options().sysFields(id=False, ins=False, upd=False, user_upd=False, group_name='!![en]System')
        tbl.column('__syscode', size=':20', unique=True, indexed=True, name_long='!![en]Internal code')
        tbl.column('name', name_long='!!Name')
        tbl.column('description', name_long='!!Description')
        tbl.column('pkg', size=':20', name_long='!!Package')
        tbl.column('checked', dtype='B', name_long='!!Checked')
        tbl.column('check_ts', dtype='DH', name_long='!!Check ts')
        tbl.column('check_user', size=':30', name_long='!!Check user')
        tbl.column('annotations', name_long='!!Annotations')
        tbl.column('doc_url', name_long='!!Documentation url', name_short='!!Url')
