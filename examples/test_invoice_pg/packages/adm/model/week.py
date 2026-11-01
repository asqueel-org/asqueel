# projects/gnrcore/packages/adm/model/week.py
# SHA256: 546e517062efdf3a9ad61c68e467b74ae2f9db7a72e39b010f5aae6d0d40829b


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('week', pkey='start_date', name_long='!![en]Week', name_plural='!![en]Week', caption_field='week')
        tbl.column('start_date', dtype='D', name_long='!![en]Start Date')
        tbl.formulaColumn('week', "to_char($start_date, 'YYYY-IW')", dtype='T', name_long='Week', static=True)
        tbl.formulaColumn('end_date', "$start_date + interval '6 days' ", dtype='D', name_long='!![en]End Date')
