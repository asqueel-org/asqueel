# projects/gnrcore/packages/adm/model/htag.py
# SHA256: cc1c146c9c1315b878a216e630cd1881cad9bf1dec99f0f08755e66d53827270


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('htag', pkey='id', name_long='!!Tag', rowcaption='$code,$description', caption_field='hierarchical_description', newrecord_caption='!!New tag')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System', syscode=True)
        tbl.options().hierarchical('code,description')
        tbl.options().counter()
        tbl.column('code', name_long='!!Code', validate_notnull=True, validate_nodup=True, unique=True)
        tbl.column('description', name_long='!!Description', validate_notnull=True)
        tbl.column('require_2fa', dtype='B', name_long='Require 2fa')
        tbl.column('isreserved', 'B', name_long='!!Reserved')
        tbl.column('note', name_long='!!Notes')
        tbl.column('linked_table', name_long='Linked table')
        tbl.formulaColumn('authorization_tag', 'COALESCE($__syscode,$hierarchical_code)', dtype='A')
