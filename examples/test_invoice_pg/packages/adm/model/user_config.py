# projects/gnrcore/packages/adm/model/user_config.py
# SHA256: da717140d0406b5cd89c470b0a38745ac940b1277d93a2c2a0fc45ce42fe885b


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('user_config', pkey='ruleid', name_long='!!User config', name_plural='!!User config')
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.column('ruleid', size=':80')
        tbl.column('user_group', size=':15', name_long='!!Group').relation('group.code', relation_name='custom_info', foreign_key=True)
        tbl.column('username', size=':32', group='_', name_long='!!User').relation('user.username', foreign_key=False, relation_name='custom_info', onDelete='cascade')
        tbl.column('pkgid', size=':50', name_long='!!Pkg').relation('pkginfo.pkgid', relation_name='rules', foreign_key=True)
        tbl.column('tblid', size=':50', name_long='!!Tbl').relation('tblinfo.tblid', relation_name='rules', foreign_key=True)
        tbl.column('data', dtype='X', name_long='!!Data')
        tbl.formulaColumn('calc_pkgid', "CASE WHEN $pkgid IS NOT NULL THEN $pkgid\n                                               WHEN $tblid IS NOT NULL THEN split_part($tblid,'.',1)\n                                               ELSE NULL END", dtype='A')
        tbl.formulaColumn('rank', 'CAST(($tblid IS NOT NULL) AS int)*8+\n                                    CAST(($pkgid IS NOT NULL) AS int)*2+\n                                    CAST(($username IS NOT NULL) AS int)*4+\n                                    CAST(($user_group IS NOT NULL) AS int)*1', dtype='L')
