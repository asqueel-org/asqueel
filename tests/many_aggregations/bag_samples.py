"""Reference values for the existing typed Bag XML codec, not a new serializer."""
from datetime import date, datetime, time, timezone
from decimal import Decimal

from genro_bag import Bag

VALUES = dict(
    code='xx<&>"\'', empty='', missing=None, integer=2,
    amount=Decimal('12.50'), real=1.25, active=True, inactive=False,
    day=date(2026, 10, 16), clock=time(12, 30),
    utc=datetime(2026, 10, 16, 12, 30, tzinfo=timezone.utc),
)
TYPES = dict(code=None, empty=None, missing='NN', integer='L', amount='N',
             real='R', active='B', inactive='B', day='D', clock='H', utc='DHZ')


def sample():
    bag = Bag()
    bag.set_item('r_0', Bag(VALUES))
    bag.set_item('r_1', Bag(dict(code='second')))
    return bag
