# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Helpers shared by the forward and reverse projection paths.

The renderer, the validator and the reader must agree on how column-name
collections are parsed and on which index attributes travel between the
tree and the JSON. Keeping the definitions here makes that agreement hold
by construction instead of by copy.
"""

#: Index attributes that travel between the element and the JSON.
INDEX_OPTIONS = ("unique", "method", "where", "tablespace", "with_options")


def split_names(value) -> list[str]:
    """Column names out of a comma-joined string, a dict or a sequence."""
    if value is None:
        return []
    if isinstance(value, dict):
        return list(value)
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value]
    return [name.strip() for name in str(value).split(",") if name.strip()]
