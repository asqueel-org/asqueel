"""The invc package; its tables are the modules of model/."""


class Package:
    def config_attributes(self):
        return dict(sqlschema='invc', sqlprefix=True, comment='invc package', name_short='Invc',
                    name_long='Invoicer')
