"""Reproduce six source-extraction probes from the legacy session audit.

Run against Genropy commit fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea.
Only Python AST definitions are executed; no framework import or database is used.
Write-order probes replace in_triggerstack with an identity decorator and use
recording adapter/table stubs. The real decorator is probed separately with a
minimal stack. These checks do not certify framework or database integration.
"""

import argparse
import ast
import json
from pathlib import Path
from types import SimpleNamespace

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("legacy_root", type=Path, help="Path to the Genropy repository checkout")
args = parser.parse_args()
root = args.legacy_root / "gnrpy" / "gnr" / "sql"
if not root.is_dir():
    parser.error(f"Legacy SQL source directory not found: {root}")


def extract(path, names, namespace):
    tree = ast.parse((root / path).read_text())
    nodes = [
        node
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names
    ]
    module = ast.Module(
        body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            *nodes,
        ],
        type_ignores=[],
    )
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)


ns = {}
extract(Path("gnrsql/helpers.py"), {"TempEnv", "in_triggerstack"}, ns)
db = SimpleNamespace(currentEnv={})
with ns["TempEnv"](db, introduced=1):
    db.currentEnv["introduced"] = 2
assert db.currentEnv == {"introduced": 2}


class Stack:
    def __init__(self):
        self.items = []

    def __bool__(self):
        return bool(self.items)

    def push(self, *args, **kwargs):
        self.items.append(args)

    def pop(self):
        self.items.pop()


ns["TriggerStack"] = Stack


@ns["in_triggerstack"]
def failed(self):
    raise RuntimeError("hook failed")


db = SimpleNamespace(currentEnv={})
try:
    failed(db)
except RuntimeError:
    pass
assert len(db.currentEnv["_trigger_stack"].items) == 1

ns = {"GnrSqlDbBaseMixin": object, "in_triggerstack": lambda fn: fn}
extract(Path("gnrsql/write.py"), {"WriteMixin"}, ns)
traces = {}
for event in ("insert", "update", "delete"):
    trace = []

    def callback(name, result=None):
        def run(*args, **kwargs):
            trace.append(name)
            return result

        return run

    table = SimpleNamespace(attributes={}, draftField="draft")
    for name in (
        "checkPkey",
        "protect_validate",
        "trigger_assignCounters",
        "trigger_releaseCounters",
        "protect_update",
        "protect_delete",
        "updateRelated",
        "deleteRelated",
        "protect_draft",
        "dbo_onInserting",
        "dbo_onUpdating",
        "dbo_onDeleting",
        "trigger_onInserting",
        "trigger_onInserted",
        "trigger_onUpdating",
        "trigger_onUpdated",
        "trigger_onDeleting",
        "trigger_onDeleted",
    ):
        setattr(table, name, callback(name))
    table._doFieldTriggers = lambda name, *a, **kw: trace.append("field:" + name)
    table._doExternalPkgTriggers = lambda name, *a, **kw: trace.append("external:" + name)
    db = ns["WriteMixin"]()
    db.adapter = SimpleNamespace(
        insert=callback("adapter:insert"),
        update=callback("adapter:update"),
        delete=callback("adapter:delete"),
    )
    db._onDbChange = callback("change")
    getattr(db, event)(table, {"id": 1})
    traces[event] = trace
assert traces["insert"] == [
    "checkPkey",
    "protect_validate",
    "field:onInserting",
    "trigger_onInserting",
    "external:onInserting",
    "trigger_assignCounters",
    "dbo_onInserting",
    "protect_draft",
    "adapter:insert",
    "change",
    "field:onInserted",
    "trigger_onInserted",
    "external:onInserted",
]
assert traces["update"] == [
    "protect_update",
    "protect_validate",
    "field:onUpdating",
    "trigger_onUpdating",
    "external:onUpdating",
    "dbo_onUpdating",
    "trigger_assignCounters",
    "adapter:update",
    "updateRelated",
    "change",
    "field:onUpdated",
    "trigger_onUpdated",
    "external:onUpdated",
]
assert traces["delete"] == [
    "protect_delete",
    "field:onDeleting",
    "trigger_onDeleting",
    "external:onDeleting",
    "deleteRelated",
    "dbo_onDeleting",
    "adapter:delete",
    "change",
    "field:onDeleted",
    "trigger_onDeleted",
    "external:onDeleted",
    "trigger_releaseCounters",
]
ns = {"Bag": type("Bag", (dict,), {})}
extract(Path("gnrsqltable/helpers.py"), {"RecordUpdater"}, ns)
updates = []
row = {"id": 1, "v": 0}
table = SimpleNamespace(
    pkey="id",
    record=lambda **kw: SimpleNamespace(output=lambda mode: row),
    update=lambda *a, **kw: updates.append((a, kw)),
)
updater = ns["RecordUpdater"](table, pkey=1, for_update=False)
assert updater.for_update is True
with updater as record:
    record["v"] = 2
assert updates[0][0][0]["v"] == 2 and updates[0][0][1]["v"] == 0
print(
    json.dumps(
        {
            "checks": 6,
            "temp_env_new_key_overwrite_survives_exit": True,
            "trigger_stack_leaks_on_error": True,
            "record_updater_false_for_update_becomes_true": True,
            "write_order": traces,
        },
        indent=2,
    )
)
