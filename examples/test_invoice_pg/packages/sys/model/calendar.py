# projects/gnrcore/packages/sys/model/calendar.py
# SHA256: 9930cb2e206bea9b1a60bedf708150d01878679e64037449ba7f3a621159f536


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('calendar', pkey='date', name_long='!![en]Calendar', name_plural='!![en]Calendar Days', caption_field='date')
        tbl.column('date', dtype='D', name_long='!![en]Date', indexed=True, unique=True)
        tbl.formulaColumn('year_month', "to_char('YYYY-MM')", dtype='L', name_long='!![en]Month')
        tbl.pyColumn('holiday', name_long='!![en]Holiday', method='pyColumn_holiday')
        tbl.formulaColumn('dow', 'EXTRACT(ISODOW FROM $date)', dtype='L')
        tbl.formulaColumn('weekend', '$dow>5', dtype='B')
        tbl.pyColumn('day_cal', dtype='A', group='*', method='templateColumn')
