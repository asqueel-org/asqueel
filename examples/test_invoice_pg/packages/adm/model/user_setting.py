# projects/gnrcore/packages/adm/model/user_setting.py
# SHA256: 95bd97ee8e32d58175d8a9059d2b16548d87465248a159f239ddc2e755162aa9


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('user_setting', pkey='identifier', pkey_columns='user_id,setting_code', name_long='User setting', name_plural='User setting', caption_field='')
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.column('user_id', size='22', group='_', name_long='User', notnull=True).relation('adm.user.id', relation_name='settings', onDelete='cascade', foreign_key=True)
        tbl.column('setting_code', size=':20', name_long='Setting code', notnull=True)
        tbl.column('setting_data', dtype='X', name_long='Setting data')
        tbl.column('identifier', size=':42', name_long='Setting identifier')
