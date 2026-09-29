"""Verify the installed SQL wheel outside the source checkout."""

import argparse
from importlib import import_module, metadata
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--postgresql', action='store_true', help='include the dedicated PostgreSQL tests')
    parser.add_argument('--core-only', action='store_true', help='verify installation without migration')
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    package = import_module('genro_sql')
    installed = Path(package.__file__).resolve().parent
    if installed.is_relative_to(repository / 'src'):
        raise RuntimeError('Wheel verification cannot use an editable installation')
    for filename in ('py.typed', 'grammar.md'):
        if not (installed / filename).is_file():
            raise RuntimeError(f'Installed wheel is missing {filename}')
    for name in ('genro_sql', 'genro_builders', 'genro_bag', 'genro_tytx', 'genro_toolbox',
                 'genro_routes', 'genro_asgi', 'genro_sqlmigration'):
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError:
            if name not in ('genro_routes', 'genro_asgi', 'genro_sqlmigration'):
                raise
            continue
        module = import_module(name)
        location = Path(module.__file__).resolve()
        if not location.is_relative_to(Path(sys.prefix).resolve()):
            raise RuntimeError(f'{name} loaded from outside the environment: {location}')
        print(f'{name}: {version}', flush=True)
    if args.core_only:
        try:
            metadata.version('genro-sqlmigration')
        except metadata.PackageNotFoundError:
            pass
        else:
            raise RuntimeError('Core-only verification requires an environment without migration')
        model = package.SqlBuilder()
        table = model.source.db('demo').schemas().schema('public').tables().table('customer', pkey='id')
        table.columns().column('id', dtype='L')
        model.validate_model()
        source = package.SqlPythonEmitter(model).emit()
        namespace = {}
        exec(compile(source, '<installed-recipe>', 'exec'), namespace)
        rebuilt = namespace['ImportedDatabase']()
        rebuilt.create()
        rebuilt.validate_model()
        print('Core-only build, validation and Python emission passed')
        return
    with tempfile.TemporaryDirectory(prefix='genro-sql-wheel-') as directory:
        destination = Path(directory)
        for name in ('tests', 'docs'):
            shutil.copytree(repository / name, destination / name)
        for name in ('README.md', 'pyproject.toml'):
            shutil.copy2(repository / name, destination / name)
        environment = dict(os.environ)
        environment.pop('PYTHONPATH', None)
        command = [sys.executable, '-m', 'pytest', 'tests', '-q', '-ra', '-o', 'addopts=',
                   '--cov=genro_sql', '--cov-report=term-missing']
        if not args.postgresql:
            command += ['-m', 'not postgresql']
        subprocess.run(command, cwd=directory, env=environment, check=True)


if __name__ == '__main__':
    main()
