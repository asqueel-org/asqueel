# projects/gnrcore/packages/adm/model/preference.py
# SHA256: ba074cf58b4bf21b1f2f6728e0a232d54728d69fd28b6e0c1d619d1d9235fa86


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('preference', pkey='code', name_long='!!Preference', name_plural='!!Preference')
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.column('code', size='12', name_long='!!Code')
        tbl.column('data', 'X', name_long='!!Data')
