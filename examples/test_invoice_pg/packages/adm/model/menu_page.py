# projects/gnrcore/packages/adm/model/menu_page.py
# SHA256: e50d123b5757086f20bea8d9254e4bd4842e956bf089c4402dc49d2bac8335cf


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('menu_page', pkey='id', name_long='!!Menu Page', name_plural='!!Menu Pages', rowcaption='$label', caption_field='label')
        tbl.options().sysFields(user_upd=False, group_name='!![en]System')
        tbl.column('label', name_long='!!Label')
        tbl.column('filepath', name_long='!!Filepath')
        tbl.column('tbl', name_long='!!Table')
        tbl.column('pkg', name_long='!!Package')
        tbl.column('metadata', name_long='!!Metadata')
