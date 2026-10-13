"""Inventory static model declarations, without importing GenroPy or opening a DB.

Usage: python inventory-test-invoice.py GENROPY_ROOT OUTPUT_JSON
The XML reader deliberately reads only package entries, never DB/auth settings.
This is evidence for grammar design, not a model loader or an execution test.
"""

import ast
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree


def inspect_file(root, path, package, role):
    source = path.read_text()
    tree = ast.parse(source)
    declarations = []
    methods = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        methods.append({"name": node.name, "line": node.lineno})
        if node.name not in {"config_db", "config_attributes", "required_packages"}:
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            if isinstance(call.func, ast.Attribute):
                name = call.func.attr
            elif isinstance(call.func, ast.Name):
                name = call.func.id
            else:
                name = ast.unparse(call.func)
            declarations.append({
                "line": call.lineno,
                "method": name,
                "arguments": [ast.unparse(arg) for arg in call.args],
                "keywords": {kw.arg or "**": ast.unparse(kw.value) for kw in call.keywords},
            })
    return {
        "package": package,
        "file": str(path.relative_to(root)),
        "role": role,
        "sha256": hashlib.sha256(source.encode()).hexdigest(),
        "bases": [ast.unparse(base) for n in tree.body if isinstance(n, ast.ClassDef) for base in n.bases],
        "methods": methods,
        "declarations": sorted(declarations, key=lambda item: item["line"]),
    }


def inventory(root):
    instance = "projects/test_invoice/instances/test_invoice_pg/instanceconfig.xml"
    packages = ElementTree.parse(root / instance).getroot().find("packages")
    if packages is None:
        raise ValueError("Missing instance packages")
    requested = [node.attrib.get("pkgcode", node.tag) for node in packages]
    pending = list(requested)
    resolved = {}
    records = []
    while pending:
        code = pending.pop(0)
        if code in resolved:
            continue
        project, name = code.split(":", 1) if ":" in code else ("test_invoice", code)
        path = root / "projects" / project / "packages" / name
        main = path / "main.py"
        tree = ast.parse(main.read_text())
        dependencies = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "required_packages":
                returns = [n for n in ast.walk(node) if isinstance(n, ast.Return)]
                if len(returns) != 1:
                    raise ValueError(f"Dynamic required_packages: {main}")
                dependencies = ast.literal_eval(returns[0].value)
        resolved[code] = {"name": name, "path": str(path.relative_to(root)), "requires": dependencies}
        pending.extend(dependencies)
        records.append(inspect_file(root, main, name, "package"))
        for model in sorted((path / "model").rglob("*.py")):
            role = "contribution" if "_packages" in model.parts else "table"
            records.append(inspect_file(root, model, name, role))
    counts = Counter(r["package"] for r in records if r["role"] != "package")
    keywords = defaultdict(set)
    for record in records:
        for decl in record["declarations"]:
            keywords[decl["method"]].update(decl["keywords"])
    support_path = root / "gnrpy/gnr/app/gnrdbo.py"
    support_source = support_path.read_text()
    return {
        "instance": instance,
        "scope": "Static source inventory; no import, model render, connection or SQL execution",
        "requested_packages": requested,
        "resolved_packages": resolved,
        "model_files_per_package": dict(counts),
        "keywords_by_method": {k: sorted(v) for k, v in sorted(keywords.items())},
        "records": records,
        "support_sources": [{
            "file": str(support_path.relative_to(root)),
            "sha256": hashlib.sha256(support_source.encode()).hexdigest(),
            "scope": "Manually inspected sysFields/helpers and AttachmentTable; not statically expanded",
        }],
        "additional_sources_to_resolve": [
            "gnrpy/gnr/app/gnrdbo.py: GnrDboTable.sysFields, helpers and AttachmentTable.config_db",
            "Package.Table mixins, generated declarations, inherited callbacks, host configuration and plugins",
        ],
    }


if __name__ == "__main__":
    result = inventory(Path(sys.argv[1]).resolve())
    Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"packages": list(result["resolved_packages"]),
                      "model_files": result["model_files_per_package"]}))
