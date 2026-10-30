# projects/gnrcore/packages/sys/model/upgrade.py
# SHA256: b256d035a05d580eeeb2575c52eb81ab0d15bfc13edde54f23ff663c3e2f9440


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('upgrade', pkey='codekey', pkey_columns='pkg,filename', pkey_columns_joiner='|', name_long='!!Upgrade ', name_plural='!!Upgrades', caption_field='codekey')
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.column('codekey', size=':306', name_long='Identifier')
        tbl.column('pkg', size=':50', name_long='Package')
        tbl.column('filename', size=':255', name_long='!!Filename')
        tbl.column('error', name_long='!!Upgrade error', name_short='!!Error')
