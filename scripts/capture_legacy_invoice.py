"""Capture the three invoice packages with the real legacy model builder, offline.

Requires a developer environment with GenroPy and its model dependencies. The
committed fixtures, and the tests consuming them, do not require GenroPy.
No instance credentials, user data, application startup callbacks or DB I/O.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch


def capture(genropy_root: Path, output_dir: Path) -> dict:
    genropy_root = genropy_root.resolve()
    from gnr.app import gnrapp
    from gnr.core.gnrbag import Bag
    from gnr.sql.gnrsql import GnrSqlDb
    from gnr.sql.gnrsqlmigration.orm_extractor import OrmExtractor

    if not Path(gnrapp.__file__).resolve().is_relative_to(genropy_root):
        raise ValueError('Imported GenroPy does not belong to --genropy-root')
    repository = Path(__file__).resolve().parents[1]
    scan = runpy.run_path(str(repository / 'docs/design/evidence/inventory-test-invoice.py'))
    inventory = scan['inventory'](genropy_root)
    packages = inventory['resolved_packages']
    instance = genropy_root / inventory['instance']
    for folder in ('custom', 'plugin'):
        path = instance.parent / folder
        if path.exists() and any(path.rglob('*.py')):
            raise ValueError(f'Additional instance contributions require explicit capture: {folder}')
    roots = {
        item['name']: str((genropy_root / item['path']).parent)
        for item in packages.values()
    }

    class OfflineApp(gnrapp.GnrApp):
        def instance_name_to_path(self, name):
            return name

        def load_instance_config(self):
            config = Bag()
            config.setItem('db', None, implementation='postgres',
                           dbname='test_invoice_pg', use_timezone=True)
            config.setItem('sysfield', None, user_ins=True, user_upd=False)
            for name, path in roots.items():
                config.setItem(f'packages.{name}', None, path=path)
            return config

        def build_package_path(self):
            self.package_path = roots.copy()

        def pkg_name_to_path(self, pkgid, project=None):
            return self.package_path[pkgid]

        def onInited(self):
            # Model construction is complete. Do not start application services.
            pass

        def check_package_dependencies(self):
            # Imports still fail normally if an actual model dependency is absent.
            pass

    attempts = []

    def deny_io(*args, **kwargs):
        attempts.append('database/network I/O')
        raise RuntimeError('Legacy oracle must not access a database or network')

    def object_node(obj):
        return {'attributes': obj.attributes,
                'children': {name: object_node(child) for name, child in obj.children.items()}}

    empty_config = Bag()
    empty_config.setItem('gnr.environment_xml', Bag())
    with TemporaryDirectory(prefix='asqueel-legacy-oracle-') as folder:
        with (
            patch.object(gnrapp, 'getGnrConfig', return_value=empty_config),
            patch.object(gnrapp, 'AppLocalizer', return_value=SimpleNamespace(
                translate=lambda value, **kwargs: value)),
            patch.object(GnrSqlDb, 'execute', deny_io),
            patch('socket.socket.connect', deny_io),
            patch('socket.socket.connect_ex', deny_io),
            patch.dict(os.environ, {'GNR_DB_DSN': ''}),
        ):
            app = OfflineApp(folder)
            structure = OrmExtractor(db=app.db).get_json_struct()
            model = object_node(app.db.model.obj)
            source = app.db.model.src.toXml()
            counts = {name: len(pkg.tables) for name, pkg in app.db.packages.items()}
        if attempts:
            raise RuntimeError('Legacy construction attempted I/O, even if it caught the error')

    imported = {}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename).resolve()
            if path.suffix == '.py' and path.is_relative_to(genropy_root):
                imported[str(path.relative_to(genropy_root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    artifacts = {
        'source.xml': source,
        'model.json': json.dumps(model, ensure_ascii=False, indent=2) + '\n',
        'physical.json': json.dumps(structure, ensure_ascii=False, indent=2) + '\n',
    }
    for filename, content in artifacts.items():
        if any(prefix in content for prefix in (str(genropy_root), folder, 'object at 0x')):
            raise ValueError(f'{filename} contains process-specific state')
    manifest = {
        'format_version': 1,
        'instance': inventory['instance'],
        'profile': {'implementation': 'postgres', 'use_timezone': True,
                    'user_ins': True, 'user_upd': False, 'tenant_schemas': [],
                    'localization': 'identity', 'application_startup': False},
        'scope': 'Actual package model build in a sanitized profile, not a live instance/DB dump',
        'packages': {key: {'name': item['name'], 'path': item['path'], 'requires': item['requires']}
                     for key, item in packages.items()},
        'table_counts': counts,
        'model_sources': [{'file': record['file'], 'sha256': record['sha256'],
                           'role': record['role']} for record in inventory['records']],
        'imported_legacy_sources': dict(sorted(imported.items())),
        'artifacts': {name: hashlib.sha256(content.encode()).hexdigest()
                      for name, content in artifacts.items()},
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in artifacts.items():
        (output_dir / name).write_text(content, encoding='utf-8')
    (output_dir / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--genropy-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    arguments = parser.parse_args()
    result = capture(arguments.genropy_root, arguments.output_dir)
    print(json.dumps({'table_counts': result['table_counts'], 'artifacts': list(result['artifacts'])}))
