# projects/gnrcore/packages/sys/model/service.py
# SHA256: da87c01ca4c9e83d93d3e326e47849208b09f10c2d52a481ae90150673e9a853


class Table:
    def config_db(self, pkg):
        tbl = pkg.table('service', name_long='!!Service', name_plural='!!Services', caption_field='service_identifier', pkey='service_identifier', pkey_columns='service_type,service_name')
        tbl.options().sysFields(id=False, user_upd=False, group_name='!![en]System')
        tbl.column('service_identifier', size=':60', name_long='!!Identifier')
        tbl.column('service_type', size=':30', name_long='!!Service type')
        tbl.column('service_name', size=':30', name_long='!!Service name')
        tbl.column('implementation', name_long='!!Implementation')
        tbl.column('parameters', dtype='X', name_long='!!Parameters')
        tbl.column('daemon', dtype='B', name_long='!!Daemon')
        tbl.column('disabled', dtype='B', name_long='!!Disabled')
