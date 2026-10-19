# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Helpers shared by the forward and reverse projection paths.

The renderer, the validator and the reader must agree on how column-name
collections are parsed and on which index attributes travel between the
tree and the JSON. Keeping the definitions here makes that agreement hold
by construction instead of by copy.
"""

#: Index attributes that travel between the element and the JSON.
INDEX_OPTIONS = ("unique", "method", "where", "tablespace", "with_options")

#: GenroPy onDelete_sql/onUpdate_sql names (any case) -> the JSON FK action.
SQL_ACTIONS = {"cascade": "CASCADE", "restrict": "RESTRICT", "no action": None,
               "setnull": "SET NULL", "set null": "SET NULL",
               "setdefault": "SET DEFAULT", "set default": "SET DEFAULT"}

#: The JSON FK action -> its GenroPy onDelete_sql/onUpdate_sql name.
SQL_ACTION_NAMES = {"CASCADE": "cascade", "RESTRICT": "restrict", "NO ACTION": "no action",
                    "SET NULL": "setnull", "SET DEFAULT": "setdefault"}

#: Column ``sql_<name>`` attributes -> the asqueel-migration JSON key they project to.
SQL_COLUMN_KEYS = {"sql_default": "sqldefault", "sql_extra": "extra_sql",
                   "sql_generatedExpression": "generated_expression"}

#: Dialect codes of the ``sql_<dialect>_<name>`` column attributes.
SQL_DIALECTS = ("pg", "sqlite")


def sql_column_attributes(attributes, implementation):
    """The ``sql_*`` column attributes on ``implementation``; ``sql_<dialect>_<name>`` wins on its dialect."""
    engine = (implementation or "sqlite").partition(":")[0]
    dialect = "pg" if engine.startswith("postgres") else engine
    result = {}
    for key in SQL_COLUMN_KEYS:
        value = attributes.get(f"sql_{dialect}_{key[4:]}", attributes.get(key))
        if value is not None:
            result[key] = value
    return result


def sql_attribute_declared(attributes, name):
    """Whether ``sql_<name>`` is declared on any dialect."""
    return any(attributes.get(f"sql_{prefix}{name}") is not None
               for prefix in ("", *(f"{dialect}_" for dialect in SQL_DIALECTS)))


def split_names(value) -> list[str]:
    """Column names out of a comma-joined string, a dict or a sequence."""
    if value is None:
        return []
    if isinstance(value, dict):
        return list(value)
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value]
    return [name.strip() for name in str(value).split(",") if name.strip()]


def default_index_name(table, columns) -> str:
    """GenroPy's index name when none is given: ``<table>_<columns joined by _>_key``."""
    return f"{table}_{'_'.join(split_names(columns))}_key"


def in_attribute_family(builder, tag, key):
    """Whether ``key`` belongs to an attribute family (``var_*``) element ``tag`` declares in its ``_meta``."""
    families = (builder._get_schema_info(tag).get('_meta') or {}).get('attribute_families', ())
    return any(key.startswith(family) and key[len(family):].isidentifier() for family in families)
