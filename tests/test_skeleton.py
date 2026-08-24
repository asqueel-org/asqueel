# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Skeleton smoke tests: the package imports and the dialect mounts."""

from genro_sql import SqlBuilder, SqlRenderer


class _EmptyModel(SqlBuilder):
    def main(self, root):
        pass  # grammar not defined yet: empty model


def test_dialect_mounts_and_creates():
    model = _EmptyModel()
    model.create()
    assert model.source is not None


def test_renderer_property_is_ephemeral():
    model = _EmptyModel()
    model.create()
    first = model.renderer_sql
    second = model.renderer_sql
    assert isinstance(first, SqlRenderer)
    assert first is not second
