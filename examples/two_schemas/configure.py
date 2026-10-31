"""Database settings and the packages folder; no database I/O."""
from pathlib import Path

from genro_bag.resolvers import EnvResolver

from asqueel import SqlDatabaseConfig

PACKAGES = Path(__file__).resolve().parent / "packages"


class DatabaseConfiguration(SqlDatabaseConfig):
    def main(self, root):
        database = self.database_section(root)
        self.packages_section(database)

    def database_section(self, root):
        database = root.db()
        database.connection(
            name=EnvResolver("PGDATABASE", default="two_schemas"),
            implementation="postgres",
            host=EnvResolver("PGHOST", default="localhost"),
            port=EnvResolver("PGPORT", default=5432, dtype="L"),
            user=EnvResolver("PGUSER", default="app"),
            password=EnvResolver("PGPASSWORD"),
        )
        return database

    def packages_section(self, database):
        database.packages(path=str(PACKAGES))
