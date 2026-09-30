# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Reserved direct-DDL renderer surface.

The implemented database projection is :class:`SqlMigrationRenderer`.
Direct DDL rendering remains outside the current package contract.
"""

from __future__ import annotations

from genro_builders.renderer import RendererBase


class SqlRenderer(RendererBase):
    """Placeholder with no direct-DDL implementation."""

    mode = "sql"
