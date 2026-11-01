# projects/gnrcore/packages/adm/model/authorization.py
# SHA256: c1b4f9bd9f66abd88248db86c43965fc432140c9b2396fded98ea868077d30e2


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('authorization', pkey='code', name_long='!!Authorization', name_plural='!!Authorizations')
        tbl.options().sysFields(id=False, user_ins=True, user_upd=False, group_name='!![en]System')
        tbl.column('code', size=':8', validate_case='U', name_long='!!Code', unmodifiable=True)
        tbl.column('user_id', size='22', name_long='!!User id').relation('user.id', foreign_key=True)
        tbl.column('use_ts', 'DH', name_long='!!Used datetime')
        tbl.column('used_by', name_long='!!Used by')
        tbl.column('note', name_long='!!Note')
        tbl.column('usage_scope', name_long='!!Use Scope')
        tbl.column('remaining_usages', 'L', name_long='!!Remaining usages', default=1)
        tbl.column('expiry_date', 'D', name_long='!!Expire Date')
