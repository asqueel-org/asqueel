"""SQL Server fixtures: skipped without pymssql or without a reachable test server."""
import os
from uuid import uuid4

import pytest


@pytest.fixture(scope='session')
def mssql_params():
    """pymssql connection fields of the test server, from GNR_TEST_MSSQL_*."""
    pymssql = pytest.importorskip('pymssql')
    if not os.environ.get('GNR_TEST_MSSQL_PASSWORD'):
        pytest.skip('SQL Server tests need GNR_TEST_MSSQL_PASSWORD')
    params = {
        'host': os.environ.get('GNR_TEST_MSSQL_HOST', '127.0.0.1'),
        'port': int(os.environ.get('GNR_TEST_MSSQL_PORT', '1433')),
        'user': os.environ.get('GNR_TEST_MSSQL_USER', 'sa'),
        'password': os.environ['GNR_TEST_MSSQL_PASSWORD'],
    }
    try:
        pymssql.connect(login_timeout=3, **params).close()
    except pymssql.OperationalError as exc:
        pytest.skip(f'SQL Server test server not reachable: {exc}')
    return params


@pytest.fixture
def mssql_database(mssql_params):
    """The connection fields of a dedicated empty database, dropped in teardown."""
    pymssql = pytest.importorskip('pymssql')
    dbname = 'test_asqueel_' + uuid4().hex[:16]
    with pymssql.connect(autocommit=True, **mssql_params) as connection:
        connection.cursor().execute(f'CREATE DATABASE "{dbname}"')
    yield dict(mssql_params, dbname=dbname)
    with pymssql.connect(autocommit=True, **mssql_params) as connection:
        cursor = connection.cursor()
        cursor.execute(f'ALTER DATABASE "{dbname}" SET SINGLE_USER WITH ROLLBACK IMMEDIATE')
        cursor.execute(f'DROP DATABASE "{dbname}"')
