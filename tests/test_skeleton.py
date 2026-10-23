# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Skeleton smoke tests: the package imports and the dialect mounts."""

from asqueel import SqlBuilder


class _EmptyModel(SqlBuilder):
    def main(self, root):
        pass  # grammar not defined yet: empty model


def test_dialect_mounts_and_creates():
    model = _EmptyModel()
    model.create()
    assert model.source is not None
