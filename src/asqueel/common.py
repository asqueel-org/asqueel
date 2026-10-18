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


def split_names(value) -> list[str]:
    """Column names out of a comma-joined string, a dict or a sequence."""
    if value is None:
        return []
    if isinstance(value, dict):
        return list(value)
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value]
    return [name.strip() for name in str(value).split(",") if name.strip()]
