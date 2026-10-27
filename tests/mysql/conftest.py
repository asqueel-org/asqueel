"""MySQL server fixtures; the tests that use them skip when no server answers.

Connection parameters come from ``GNR_TEST_MYSQL_HOST``, ``GNR_TEST_MYSQL_PORT``,
``GNR_TEST_MYSQL_USER`` and ``GNR_TEST_MYSQL_PASSWORD``, defaulting to
127.0.0.1:3306 as root without a password. A local server::

    docker run -d --name asqueel-mysql-test -e MYSQL_ROOT_PASSWORD=asqueel \\
        -p 127.0.0.1:13306:3306 mysql:8.4
    GNR_TEST_MYSQL_PORT=13306 GNR_TEST_MYSQL_PASSWORD=asqueel pytest -m mysql
"""
import os
from uuid import uuid4

import pytest


@pytest.fixture(scope='session')
def mysql_params():
    """Connection fields of the test server, as the adapter's connect takes them."""
    pymysql = pytest.importorskip('pymysql')
    params = {
        'host': os.environ.get('GNR_TEST_MYSQL_HOST', '127.0.0.1'),
        'port': int(os.environ.get('GNR_TEST_MYSQL_PORT', '3306')),
        'user': os.environ.get('GNR_TEST_MYSQL_USER', 'root'),
        'connect_timeout': 3,
    }
    if os.environ.get('GNR_TEST_MYSQL_PASSWORD'):
        params['password'] = os.environ['GNR_TEST_MYSQL_PASSWORD']
    try:
        pymysql.connect(**params).close()
    except pymysql.err.OperationalError as exc:
        pytest.skip(f'No MySQL server answers: {exc}')
    return params


@pytest.fixture
def mysql_server(mysql_params):
    """``(params, prefix)``: a default database is created; every database named ``prefix*`` is dropped at teardown.

    SQL schemas are MySQL databases, so a test names its schemas with ``prefix``.
    """
    import pymysql

    prefix = 'asqueel_test_' + uuid4().hex[:12]
    observer = pymysql.connect(**mysql_params, autocommit=True)
    try:
        with observer.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE `{prefix}`')
        yield dict(mysql_params, dbname=prefix), prefix
    finally:
        with observer.cursor() as cursor:
            cursor.execute('SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE %s',
                           (prefix + '%',))
            for (name,) in cursor.fetchall():
                cursor.execute(f'DROP DATABASE `{name}`')
        observer.close()
