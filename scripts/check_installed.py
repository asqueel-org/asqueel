"""Verify the installed SQL wheel outside the source checkout."""

import argparse
from importlib import import_module, metadata
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--postgresql', action='store_true', help='include the dedicated PostgreSQL tests')
    parser.add_argument('--core-only', action='store_true', help='verify installation without migration')
    parser.add_argument('--coverage-xml', type=Path, help='save coverage with repository source paths')
    args = parser.parse_args()
    if args.core_only and args.coverage_xml:
        parser.error('--coverage-xml requires the test suite')
    repository = Path(__file__).resolve().parents[1]
    package = import_module('asqueel')
    installed = Path(package.__file__).resolve().parent
    if installed.is_relative_to(repository / 'src'):
        raise RuntimeError('Wheel verification cannot use an editable installation')
    for filename in ('py.typed', 'grammar.md'):
        if not (installed / filename).is_file():
            raise RuntimeError(f'Installed wheel is missing {filename}')
    for name in ('asqueel', 'genro_builders', 'genro_bag', 'genro_tytx', 'genro_toolbox',
                 'genro_routes', 'genro_asgi', 'asqueel_migration'):
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError:
            if name not in ('genro_routes', 'genro_asgi', 'asqueel_migration'):
                raise
            continue
        module = import_module(name)
        location = Path(module.__file__).resolve()
        if not location.is_relative_to(Path(sys.prefix).resolve()):
            raise RuntimeError(f'{name} loaded from outside the environment: {location}')
        print(f'{name}: {version}', flush=True)
    if args.core_only:
        try:
            metadata.version('asqueel-migration')
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
        resolved = package.resolve_model(rebuilt)
        query = package.PostgresCompiler(resolved).select(
            'public.customer', where='$id = :id', sqlparams={'id': 7},
        )
        assert query.params == {'id': 7}
        assert '"public"."customer"' in query.sql
        generic = package.QueryCompiler(
            resolved, package.PostgresDialect(), package.PsycopgDriver(),
        ).select('public.customer', where='$id = :id', sqlparams={'id': 7})
        assert generic == query
        print('Core-only build, validation, emission, model and adapter pipeline passed')
        return
    with tempfile.TemporaryDirectory(prefix='asqueel-wheel-') as directory:
        destination = Path(directory)
        for name in ('tests', 'docs', 'examples'):
            shutil.copytree(repository / name, destination / name)
        for name in ('README.md', 'pyproject.toml'):
            shutil.copy2(repository / name, destination / name)
        environment = dict(os.environ)
        environment.pop('PYTHONPATH', None)
        command = [sys.executable, '-m', 'pytest', 'tests', '-q', '-ra', '-o', 'addopts=',
                   '--cov=asqueel', '--cov-report=term-missing']
        if args.coverage_xml:
            command += [f'--cov-report=xml:{destination / "coverage.xml"}']
        if not args.postgresql:
            command += ['-m', 'not postgresql']
        subprocess.run(command, cwd=directory, env=environment, check=True)
        if args.coverage_xml:
            report = ET.parse(destination / 'coverage.xml')
            sources = report.find('sources')
            if sources is None:
                raise RuntimeError('Coverage report has no source paths')
            sources.clear()
            ET.SubElement(sources, 'source').text = '.'
            for entry in report.iter('class'):
                filename = Path(entry.attrib['filename'])
                if filename.is_absolute():
                    filename = filename.relative_to(installed)
                relative = Path('src/asqueel') / filename
                if not (repository / relative).is_file():
                    raise RuntimeError(f'Coverage source not found: {relative}')
                entry.set('filename', relative.as_posix())
            output = args.coverage_xml.resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            report.write(output, encoding='utf-8', xml_declaration=True)
            print(f'Coverage report: {output}', flush=True)


if __name__ == '__main__':
    main()
