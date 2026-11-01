# projects/test_invoice/packages/invc/model/staff_role.py
# SHA256: a5b8935b7f165eeddf85d12dd8ecce432e26308b2926fdcbe9560dcabfe2286e


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('staff_role', pkey='code', name_long='!!Staff Role', name_plural='!!Staff Roles', caption_field='description', lookup=True)
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.column('code', size=':5', name_long='!!Code')
        tbl.column('description', name_long='!!Description')
