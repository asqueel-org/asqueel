"""Configuration-based CLI and Python console; migration work stays in its package."""
from __future__ import annotations

import argparse
import code
import sys

from .application import AsqueelDb
from .configuration import connection_settings
from .errors import MigrationError
from .registry import DatabaseRegistry, RegistrationError


def write_line(message, *, file=None):
    """Terminal output lives at the CLI boundary only."""
    stream = file if file is not None else sys.stdout
    stream.write(str(message) + '\n')


class CliError(ValueError):
    """An actionable CLI error containing no connection credentials."""


def parser():
    result = argparse.ArgumentParser(prog='asqueel')
    commands = result.add_subparsers(dest='command', required=True)
    register = commands.add_parser('register', help='Register a folder containing configure.py')
    register.add_argument('name')
    register.add_argument('folder')
    commands.add_parser('list', help='List registered database configurations')
    unregister = commands.add_parser('unregister', help='Remove a registration only')
    unregister.add_argument('name')
    for command in ('check', 'shell'):
        target_arguments(commands.add_parser(command, help=(
            'Validate a configuration offline' if command == 'check'
            else 'Open a Python console with db available')))
    database = commands.add_parser('db', help='Compare or migrate physical structure')
    operations = database.add_subparsers(dest='operation', required=True)
    for operation in ('plan', 'apply'):
        operation_parser = operations.add_parser(operation)
        target_arguments(operation_parser)
        operation_parser.add_argument('--allow-removals', action='store_true',
                                      help='Enable supported removals (currently columns, not whole tables)')
    return result


def target_arguments(command):
    command.add_argument('target', nargs='?', help='Registered name, folder, file or module:Class')
    command.add_argument('--config', help='Explicit configuration source, instead of a target')


def run_migration(db, operation, *, allow_removals=False):
    """Print the plan; on apply, migrate and confirm. Errors reach ``main``."""
    plan = (db.migration_plan(allow_removals=allow_removals) if operation == 'plan'
            else db.migrate(allow_removals=allow_removals))
    for warning in plan.warnings:
        write_line(f'Warning: {warning}', file=sys.stderr)
    if plan.empty:
        write_line('No changes.')
        return 0
    write_line(plan.commands)
    if operation == 'apply':
        write_line('Migration applied. No remaining commands under the selected removal policy.')
    return 0


def run(options):
    registry = DatabaseRegistry()
    if options.command == 'register':
        registry.register(options.name, options.folder)
        write_line(f'Registered {options.name}.')
        return 0
    if options.command == 'list':
        for name in registry.names():
            write_line(f'{name}\t{registry.resolve(name).parent}')
        return 0
    if options.command == 'unregister':
        registry.remove(options.name)
        write_line(f'Unregistered {options.name}; project files and database unchanged.')
        return 0
    if options.target and options.config:
        raise CliError('Choose either a target or --config')
    source = options.config or options.target or '.'
    db = AsqueelDb(source)
    try:
        if options.command == 'check':
            # Read through the handler to validate resolvers without database I/O.
            connection_settings(db.config)
            write_line(f'Configuration valid: {len(db.model.tables)} tables.')
            return 0
        if options.command == 'shell':
            code.interact(
                banner='Asqueel Python console: db is ready. Use db.commit() or db.rollback().\n'
                       'Leaving the console rolls back pending work and closes the database.',
                local={'db': db}, exitmsg='Database closed on console exit.',
            )
            return 0
        return run_migration(db, options.operation, allow_removals=options.allow_removals)
    finally:
        db.close()


def main(argv=None):
    options = parser().parse_args(argv)
    try:
        return run(options)
    except (CliError, RegistrationError, MigrationError) as error:
        write_line(f'Error: {error}', file=sys.stderr)
    except ModuleNotFoundError as error:
        if error.name == 'asqueel_migration':
            write_line('Install asqueel[migration] for database commands.', file=sys.stderr)
        elif error.name == 'psycopg':
            write_line('Install asqueel[postgresql] for PostgreSQL databases.', file=sys.stderr)
        else:
            write_line('Configuration import failed; ensure its Python dependencies are importable.', file=sys.stderr)
    except KeyboardInterrupt:
        write_line('Interrupted.', file=sys.stderr)
        return 130
    except Exception as error:
        # Grammar/driver exceptions can embed resolved secrets. Never echo arbitrary
        # exception text or a traceback at the terminal boundary.
        write_line(f'Error ({type(error).__name__}): check the configuration, registration and database access.',
              file=sys.stderr)
        if hasattr(error, 'partial_state_possible'):
            write_line(f'DDL rolled back: {error.rolled_back}; partial state possible: '
                  f'{error.partial_state_possible}. Inspect the plan before retrying.', file=sys.stderr)
    return 1
