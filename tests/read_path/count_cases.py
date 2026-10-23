"""Reusable count assertions executed by the public terminal tests."""

def test_count_uses_the_environment(shop, statements):
    query = shop.query(columns='$id', where='$customer_id IN :env_customers')
    with shop.db.tempEnv(customers=[1]):
        assert query.count() == 2
    with shop.db.tempEnv(customers=[1, 2, 3]):
        assert query.count() == 4

def test_count_does_not_commit(shop, statements):
    shop.db.execute(f'INSERT INTO {shop.invoice_sql} (id, customer_id, total) '
                    'VALUES (:id, :customer, :total)', {'id': 16, 'customer': 3, 'total': 1})
    assert shop.query(columns='$id').count() == 6
    shop.db.rollback()
    assert shop.query(columns='$id').count() == 5
