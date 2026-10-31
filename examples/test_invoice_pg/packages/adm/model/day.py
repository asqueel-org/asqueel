# projects/gnrcore/packages/adm/model/day.py
# SHA256: c30d7f03c80d4c9e84dea55821b9e491357653eda9a12df323d2edd9022738ca


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('day', pkey='date', name_long='!!Days', name_plural='!!Days', caption_field='date')
        tbl.column('date', dtype='D', name_long='!!Date')
        tbl.column('weekday', dtype='L', name_long='!!Weekday')
        tbl.column('is_holyday', dtype='B', name_long='!!Is holyday')
