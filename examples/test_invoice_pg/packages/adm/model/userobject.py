# projects/gnrcore/packages/adm/model/userobject.py
# SHA256: 95f1eda3d637ab8c3266a1d5557d0db30a6e8ceef8beacdeee80547638ac031c


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('userobject', pkey='id', name_long='!![en]User Object', name_plural='!![en]User Objects', rowcaption='$code,$objtype')
        tbl.options().broadcast('objtype')
        tbl.options().archive()
        tbl.options().sysFields(id=True, ins=True, upd=True, user_upd=False, group_name='!![en]System')
        tbl.column('identifier', size=':120', indexed=True, sql_value="COALESCE(:tbl,:pkg,'')||:objtype||:code|| CASE WHEN :private THEN :userid ELSE '' END", unique=True)
        tbl.column('code', size=':40', name_long='!![en]Code', indexed=True, validate_notnull=True)
        tbl.column('objtype', size=':20', name_long='!![en]Object Type', indexed=True)
        tbl.column('pkg', size=':50', name_long='!![en]Package', default_from='@tbl.pkgid').relation('pkginfo.pkgid', foreign_key=False, relation_name='objects')
        tbl.column('tbl', size=':50', name_long='!![en]Table').relation('tblinfo.tblid', foreign_key=False, relation_name='objects')
        tbl.column('userid', size=':50', name_long='!![en]User ID', indexed=True)
        tbl.column('description', size=':50', name_long='!![en]Description', indexed=True)
        tbl.column('notes', 'T', name_long='!![en]Notes')
        tbl.column('data', 'X', name_long='!![en]Data')
        tbl.column('authtags', 'T', name_long='!![en]Auth tags')
        tbl.column('private', 'B', name_long='!![en]Private')
        tbl.column('quicklist', 'B', name_long='!![en]Quicklist')
        tbl.column('flags', 'T', name_long='!![en]Flags')
        tbl.column('required_pkg', name_long='!![en]Required pkg')
        tbl.column('preview', name_long='!![en][it]Preview')
        tbl.formulaColumn('system_userobject', '$code LIKE :scode', var_scode='\\_\\_%%', dtype='B')
        tbl.pyColumn('resource_status', name_long='!![en]Resources', required_columns='$data', method='pyColumn_resource_status')
        tbl.formulaColumn('is_mail', ":email ILIKE ANY(string_to_array($flags,','))", var_email='is_mail', dtype='B', static=True)
        tbl.formulaColumn('is_row', ":row ILIKE ANY(string_to_array($flags,','))", var_row='is_row', dtype='B', static=True)
        tbl.formulaColumn('is_print', ":print ILIKE ANY(string_to_array($flags,','))", var_print='is_print', dtype='B', static=True)
