"""Use the same disposable PostgreSQL service for every acceptance suite."""
import os

from psycopg.conninfo import make_conninfo


def postgres_dsn():
    if os.environ.get('ASQUEEL_TEST_DSN'):
        return os.environ['ASQUEEL_TEST_DSN']
    parameters = {
        'host': os.environ.get('GNR_TEST_PG_HOST', '127.0.0.1'),
        'port': os.environ.get('GNR_TEST_PG_PORT', '5432'),
        'user': os.environ.get('GNR_TEST_PG_USER', 'postgres'),
        'dbname': 'postgres',
        'connect_timeout': 3,
    }
    if os.environ.get('GNR_TEST_PG_PASSWORD'):
        parameters['password'] = os.environ['GNR_TEST_PG_PASSWORD']
    return make_conninfo(**parameters)
