"""The sales package; its tables are the modules of model/."""


class Package:
    def config_attributes(self):
        return dict(sqlschema='sales', sqlprefix=False)
