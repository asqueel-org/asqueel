# projects/gnrcore/packages/adm/model/tblinfo_item.py
# SHA256: 97a7af17cabfb43a7bad4f47116cb590d418987e11a54c12f5e9dfe15849c70f


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('tblinfo_item', pkey='info_key', pkey_columns='tblid,item_type,code', name_long='!!Tblinfo item', pkey_columns_joiner='/', name_plural='!!Tblinfo items', caption_field='description')
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.column('info_key', size=':50', readOnly=True, name_long='!!Info key', indexed=True)
        tbl.column('code', size=':50', name_long='!!Code')
        tbl.column('description', size=':50', name_long='!!Description')
        tbl.column('item_type', size=':5', name_long='!!Type', validate_values='QTREE:Quick tree,FTREE:Full tree')
        tbl.column('data', dtype='X', name_long='!!Data')
        tbl.column('tblid', size=':50').relation('tblinfo.tblid', relation_name='items', onDelete='cascade', foreign_key=True)
