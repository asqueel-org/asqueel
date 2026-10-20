# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Helpers shared by the forward and reverse projection paths.

The renderer, the validator and the reader must agree on how column-name
collections are parsed and on which index attributes travel between the
tree and the JSON. Keeping the definitions here makes that agreement hold
by construction instead of by copy.
"""

#: Index attributes that travel between the element and the JSON.
INDEX_OPTIONS = ("unique", "method", "where", "tablespace", "with_options")

#: GenroPy onDelete_sql/onUpdate_sql names and abbreviations (any case) -> the JSON FK action,
#: as legacy ``statement_converter``.
SQL_ACTIONS = {"c": "CASCADE", "cascade": "CASCADE", "r": "RESTRICT", "restrict": "RESTRICT",
               "n": None, "no action": None,
               "sn": "SET NULL", "setnull": "SET NULL", "set null": "SET NULL",
               "sd": "SET DEFAULT", "setdefault": "SET DEFAULT", "set default": "SET DEFAULT"}

#: Keys of a column ``indexed={...}``, besides ``with_<name>``, as legacy ``fill_json_column_index``.
INDEXED_KEYS = ("unique", "method", "where", "tablespace", "sorting")

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


def unknown_indexed_keys(indexed) -> list[str]:
    """The keys of an ``indexed={...}`` dict that legacy ``fill_json_column_index`` does not read."""
    if not isinstance(indexed, dict):
        return []
    return sorted(key for key in indexed if key not in INDEXED_KEYS and not key.startswith("with_"))


def indexed_attributes(columns, indexed):
    """The index attributes ``indexed=`` declares on ``columns``, as legacy ``fill_json_column_index``.

    ``None`` when the declaration makes the column unique instead (``unique`` without ``where``).
    """
    spec = dict(indexed) if isinstance(indexed, dict) else {}
    with_options = {key[5:]: spec.pop(key) for key in list(spec) if key.startswith("with_")}
    sorting = spec.pop("sorting", None)
    if spec.get("unique") and not spec.get("where"):
        return None
    attributes = {"columns": dict(zip(columns, sorting.split(",") if sorting else [None] * len(columns)))}
    attributes.update((key, value) for key, value in spec.items() if value)
    if with_options:
        attributes["with_options"] = with_options
    return attributes


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
