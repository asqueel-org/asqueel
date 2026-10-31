# projects/test_invoice/packages/invc/model/staff.py
# SHA256: 4d315c52b346ce233df251ec2f7db514f01dd4e303698cbbd3b31a273e7f08b9


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('staff', pkey='id', name_long='!!Staff', name_plural='!!Staff Members', caption_field='full_name')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('first_name', name_long='!!First Name', validate_notnull=True)
        tbl.column('last_name', name_long='!!Last Name', validate_notnull=True)
        tbl.column('email', name_long='!!Email')
        tbl.column('hire_date', dtype='D', name_long='!!Hire Date')
        tbl.column('state', size=':5', name_long='!!State').relation('invc.state.code', relation_name='staff_members', onDelete='raise', foreign_key=True)
        tbl.column('role_code', size=':5', name_long='!!Role').relation('staff_role.code', relation_name='staff_members', onDelete='raise', foreign_key=True)
        tbl.column('user_id', size='22', name_long='!!User').relation('adm.user.id', relation_name='staff_member', onDelete='setnull', foreign_key=True)
        tbl.formulaColumn('full_name', sql_formula="$first_name || ' ' || $last_name", dtype='T', name_long='Full Name')
        tbl.aliasColumn('state_name', relation_path='@state.name', name_long='State Name')
        tbl.aliasColumn('role_description', relation_path='@role_code.description', name_long='Role Description')
        tbl.aliasColumn('region_name', relation_path='@state.@region_code.name', name_long='Region Name')
        tbl.aliasColumn('username', relation_path='@user_id.username', name_long='Username')
