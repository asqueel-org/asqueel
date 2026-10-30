# projects/gnrcore/packages/adm/model/api_token.py
# SHA256: 898e68417949db2b2989bb026a2fa03741416b5c15c864b8a3308da5488d4370


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('api_token', pkey='id', name_long='!!API Token', name_plural='!!API Tokens', rowcaption='$description')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('token', size='64', unique=True, indexed=True, name_long='!!Token')
        tbl.column('description', name_long='!!Description')
        tbl.column('group_code', size=':15', name_long='!!Group').relation('group.code', relation_name='api_tokens', foreign_key=True)
        tbl.column('is_active', dtype='B', default=True, name_long='!!Active')
        tbl.column('expires_ts', dtype='DHZ', name_long='!!Expires')
        tbl.column('activated_ts', dtype='DHZ', name_long='!!Activated')
        tbl.column('last_used_ts', dtype='DHZ', name_long='!!Last Used')
        tbl.column('created_by', size='22', group='_', name_long='!!Created By').relation('adm.user.id', foreign_key=False, relation_name='api_tokens', onDelete='setnull')
        tbl.column('notes', dtype='T', name_long='!!Notes')
        tbl.column('token_hint', size='8', name_long='!!Token Hint')
        tbl.formulaColumn('all_tags', select=dict(table='adm.api_token_tag', columns='@tag_id.authorization_tag', where='$api_token_id=#THIS.id'), dtype='A', name_long='!!Tags')
        tbl.formulaColumn('status', "CASE\n                 WHEN $token IS NULL THEN 'to_activate'\n                 WHEN $is_active IS NOT TRUE THEN 'inactive'\n                 WHEN $expires_ts IS NOT NULL AND $expires_ts < CURRENT_TIMESTAMP THEN 'expired'\n                 ELSE 'active'\n               END", dtype='A', name_long='!!Status')
