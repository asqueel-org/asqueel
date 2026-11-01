# projects/gnrcore/packages/adm/model/letterhead_type.py
# SHA256: 114c622198873165bf4ce131aa830cfd6d54d4abcedf23e0c02c428ca31311e8


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('letterhead_type', pkey='code', name_long='Letterhead type', name_plural='Letterhead types', lookup=True)
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.column('code', size=':15', name_long='!!Code', indexed=True, unique=True, validate_notnull='Required')
        tbl.column('description', name_long='!!Description')
