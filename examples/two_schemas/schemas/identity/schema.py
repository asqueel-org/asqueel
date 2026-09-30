"""Explicit table imports; no folder discovery."""
from .user import UserModel
from .access import AccessModel


class IdentitySchema:
    def configure(self, schemas):
        schema = schemas.schema("identity")
        tables = schema.tables()
        UserModel().configure(tables)
        AccessModel().configure(tables)
        return schema
