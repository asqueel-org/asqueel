# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Projection of a SQL model tree into the Python recipe that rebuilds it.

The last leg of the reverse pipeline: a live database read as normalized
JSON becomes a source tree through
:class:`~asqueel.reader.SqlModelReader`, and a source tree becomes
a module a person can open and maintain here. The law is the same one the
reader answers to, one step further out::

    render(exec(builder.render(mode='python')).create()) == render(builder)

so the rendered module is not a report about the model — it *is* the model,
in the only form a developer edits.

Literal mode: every element of the tree is emitted as the call that built
it, with the attributes it actually carries. No sugar is re-derived
(``indexed=`` stays whatever the tree says, an index stays an ``index``
element), and nothing is invented. An ``idiomatic`` mode — folding indexes
back into ``indexed=True``, chaining what reads better chained — would be a
different projection and belongs to its own class.

Determinism is a contract, not a courtesy: two emissions of the same tree
are byte-identical, and so are two emissions of two trees read from the
same structure. It comes from taking every ordering decision from the
model itself — tree order for the elements, signature order for the
keyword arguments — never from a set or a dict comprehension over
attributes.

Hash-named indexes are the one place where a derived name reaches the
emitted source, and it is not a choice: ``table`` is a name-keyed
collection, so an index without a name cannot be built at all, and the
index ``name`` IS the physical ``index_name`` the renderer echoes. An
index read back from a database that never named it therefore travels as
``name="idx_<hash>"`` — the alternative would rename the index.
"""

from __future__ import annotations

import inspect
import keyword
import re

from genro_builders.renderer import RendererBase

#: Names the emitted ``main`` body must not shadow.
_RESERVED = frozenset({"self", "root", "db"})

#: Maximum width of an emitted line, ``[tool.ruff] line-length``.
_WIDTH = 100

_HEADER = '''"""SqlBuilder recipe emitted by asqueel.emitter.

Literal projection of a normalized SQL structure: ordinary source, meant
to be edited by hand from here on.
"""
from __future__ import annotations

from asqueel import SqlBuilder
'''


def _literal(value) -> str:
    """A Python literal for an attribute value, double-quoted by preference.

    ``repr`` is the authority on escaping; the single quotes it prefers are
    swapped for double ones only when that is a pure requoting.
    """
    if isinstance(value, str):
        text = repr(value)
        if text.startswith("'") and '"' not in text and "\\" not in text:
            return f'"{text[1:-1]}"'
        return text
    if isinstance(value, dict):
        items = ", ".join(f"{_literal(key)}: {_literal(item)}"
                          for key, item in value.items())
        return f"{{{items}}}"
    if isinstance(value, (list, tuple)):
        items = ", ".join(_literal(item) for item in value)
        if isinstance(value, list):
            return f"[{items}]"
        if not value:
            return "()"
        suffix = "," if len(value) == 1 else ""
        return f"({items}{suffix})"
    return repr(value)


def _identifier(name: str, taken: set[str]) -> str:
    """A free Python identifier for a SQL name.

    SQL names live in their own namespace — they are emitted as string
    literals — so this only has to produce something legal and unique.
    """
    candidate = re.sub(r"\W", "_", str(name))
    if not candidate or candidate[0].isdigit():
        candidate = f"_{candidate}"
    if keyword.iskeyword(candidate) or keyword.issoftkeyword(candidate):
        candidate = f"{candidate}_"
    unique, counter = candidate, 1
    while unique in taken:
        counter += 1
        unique = f"{candidate}_{counter}"
    taken.add(unique)
    return unique


class SqlPythonEmitter(RendererBase):
    """Render the Python recipe that rebuilds a SQL model tree.

    Reached as ``recipe.render(mode='python', class_name='ImportedDatabase')``.
    Each node renders to a fragment carrying its tag, name, call arguments
    and child fragments; ``finalize`` names the variables in tree order and
    writes the module, so no walk state survives to it.

    There is deliberately no ``# TODO`` path for "preserved but
    unrepresentable" features: :class:`~asqueel.reader.SqlModelReader`
    rejects unsupported schema features before they reach the tree. Readable FK
    names are explicitly non-semantic migration metadata, not preserved recipe
    features.
    """

    mode = "python"
    render_type = "string"

    def get_render(self, builder):
        # A mounted subtree is written as calls of this same recipe.
        return self

    def rendered_item(self, node, item, runtime_attrs, *, tag, **opts):
        return {"tag": node.node_tag, "name": node.get_attr("name"),
                "arguments": self._arguments(node),
                "children": item if isinstance(item, list) else []}

    def finalize(self, result, target, class_name: str = "ImportedDatabase", **_opts):
        """Write the module from the fragments and deliver it to ``target``.

        Args:
            class_name: the name of the rendered ``SqlBuilder`` subclass.
        """
        if (not class_name.isidentifier() or keyword.iskeyword(class_name)
                or keyword.issoftkeyword(class_name)):
            raise ValueError(f"invalid emitted class name: {class_name!r}")
        database = next((fragment for fragment in result if fragment["tag"] == "db"), None)
        if database is None:
            raise ValueError("cannot emit an empty SQL model without a database")
        taken = set(_RESERVED)
        lines = [
            _HEADER, "",
            f"class {class_name}(SqlBuilder):",
            '    """Recipe of a database read from its normalized structure."""',
            "",
            "    def main(self, root):",
        ]
        body: list[str] = []
        body.append(_statement("db", "root", database))
        for collection in database["children"]:
            body.append("")
            _emit_collection(collection, "db", body, taken)
        for statement in body:
            lines.extend(f"        {line}" if line else ""
                         for line in statement.split("\n"))
        return super().finalize("\n".join(lines) + "\n", target)

    def _arguments(self, node) -> list[tuple[str, object]]:
        """The node's attributes in signature order, extras last.

        The element signature is the canonical order — the same order the
        grammar documents — so a renamed or reordered parameter moves the
        rendered recipe with it instead of drifting from it.
        """
        attributes = {key: value for key, value in node.attr.items()
                      if not key.startswith("_")}
        declared = self._signature(node.node_tag)
        ordered = [(name, attributes.pop(name)) for name in declared
                   if name in attributes]
        return ordered + sorted(attributes.items())

    def _signature(self, tag) -> tuple[str, ...]:
        """Parameter names of an element, in declaration order."""
        marker = getattr(type(self.builder), tag)
        parameters = inspect.signature(marker._func).parameters.values()
        return tuple(parameter.name for parameter in parameters
                     if parameter.name != "self"
                     and parameter.kind is not parameter.VAR_KEYWORD)


def _emit_owner(fragment, target, body, taken) -> None:
    variable = _identifier(fragment["name"], taken)
    body.append(_statement(variable, target, fragment))
    for collection in fragment["children"]:
        _emit_collection(collection, variable, body, taken)


def _emit_collection(fragment, target, body, taken) -> None:
    variable = _identifier(fragment["tag"], taken)
    body.append(_statement(variable, target, fragment))
    for child in fragment["children"]:
        if child["tag"] in ("schema", "table"):
            body.append("")
            _emit_owner(child, variable, body, taken)
            continue
        descendants = child["children"]
        if not descendants:
            body.append(_statement(None, variable, child))
            continue
        owner = _identifier(child["name"], taken)
        body.append(_statement(owner, variable, child))
        for descendant in descendants:
            body.append(_statement(None, owner, descendant))


def _statement(variable, target, fragment) -> str:
    """One call, assigned to ``variable`` when something reads it back."""
    head = f"{target}.{fragment['tag']}("
    if variable:
        head = f"{variable} = {head}"
    arguments = [f"{name}={_literal(value)}" for name, value in fragment["arguments"]]
    return _wrap(head, arguments)


def _wrap(head, arguments) -> str:
    """The call on one line, or with its arguments packed and indented."""
    single = f"{head}{', '.join(arguments)})"
    if len(single) + 8 <= _WIDTH:
        return single
    lines, current = [], ""
    for argument in arguments:
        candidate = f"{current} {argument}," if current else f"{argument},"
        if current and len(candidate) + 12 > _WIDTH:
            lines.append(current)
            current = f"{argument},"
        else:
            current = candidate
    lines.append(current)
    packed = "\n".join(f"    {line}" for line in lines)
    return f"{head}\n{packed}\n)"


__all__ = ["SqlPythonEmitter"]
