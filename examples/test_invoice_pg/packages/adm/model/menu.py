# projects/gnrcore/packages/adm/model/menu.py
# SHA256: 724f702d49e10f513c8d96257437d76927560437603148f006e3ab2f167584fe


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('menu', pkey='id', name_long='!!Menu Directory', name_plural='!!Menu Directories', rowcaption='$hierarchical_label', caption_field='hierarchical_label')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.options().hierarchical('label')
        tbl.options().counter()
        tbl.column('label', name_long='!!Label')
        tbl.column('tags', name_long='!!Tags')
        tbl.column('summary', name_long='!!Summary')
        tbl.column('ts_import', dtype='DH')
        tbl.column('page_id', size='22').relation('menu_page.id', relation_name='links', foreign_key=True)
        tbl.aliasColumn('page_label', relation_path='@page_id.label')
        tbl.aliasColumn('page_filepath', relation_path='@page_id.filepath')
        tbl.aliasColumn('page_tbl', relation_path='@page_id.tbl')
        tbl.aliasColumn('page_metadata', relation_path='@page_id.metadata')
