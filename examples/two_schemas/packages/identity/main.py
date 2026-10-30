"""The identity package; its tables are the modules of model/."""


class Package:
    def config_attributes(self):
        return dict(sqlschema='identity', sqlprefix=False)
