"""The adm package; its tables are the modules of model/."""


class Package:
    def config_attributes(self):
        return dict(sqlschema='adm', comment='Admin', name_short='Adm', name_long='!!Administration')
