# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Phase 11 contract — grammar documentation uses public builder APIs."""
from __future__ import annotations

import ast
from pathlib import Path

from genro_sql import grammar_doc


def test_grammar_doc_imports_no_private_genro_builders_module():
    source = Path(grammar_doc.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(
        module.startswith("genro_builders.") and "._" in module
        for module in imported
    )


def test_public_export_keeps_the_committed_document_current():
    committed = grammar_doc.DOC_PATH.read_text(encoding="utf-8")
    assert grammar_doc.generate_grammar_md() == committed
