"""Database settings and explicit schema composition; no database I/O."""
from genro_bag.resolvers import EnvResolver

from asqueel import SqlDatabaseConfig

from examples.two_schemas.schemas.identity.schema import IdentitySchema
from examples.two_schemas.schemas.sales.schema import SalesSchema


class DatabaseConfiguration(SqlDatabaseConfig):
    def main(self, root):
        database = self.database_section(root)
        self.schemas_section(database)

    def database_section(self, root):
        database = root.db()
        database.connection(
            name=EnvResolver("PGDATABASE", default="two_schemas"),
            implementation="postgresql",
            host=EnvResolver("PGHOST", default="localhost"),
            port=EnvResolver("PGPORT", default=5432, dtype="L"),
            user=EnvResolver("PGUSER", default="app"),
            password=EnvResolver("PGPASSWORD"),
        )
        return database

    def schemas_section(self, database):
        schemas = database.schemas()
        IdentitySchema().configure(schemas)
        SalesSchema().configure(schemas)
