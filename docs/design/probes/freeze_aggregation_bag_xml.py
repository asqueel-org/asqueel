"""Freeze the existing typed XML wire, using Bag and the real GenroPy catalog.

Run from the repository with src, GenroPy gnrpy and its dependencies available
on PYTHONPATH. This is an optional oracle-generation tool, not a core dependency.
"""
import hashlib
from importlib.metadata import version
import inspect
import json
from pathlib import Path

from genro_bag import Bag
from genro_bag import _legacy_codec
from gnr.core.gnrclasses import GnrClassCatalog
from tests.many_aggregations.bag_samples import sample

root = Path(__file__).resolve().parents[3]
target = root / 'tests/many_aggregations/data'
catalog = GnrClassCatalog()
for name, value in [('rows', sample()), ('empty', Bag())]:
    (target / f'{name}.xml').write_text(value.to_xml(legacy_mode=True, catalog=catalog))
files = [Path(inspect.getfile(_legacy_codec)), Path(inspect.getfile(GnrClassCatalog))]
metadata = dict(
    bag_version=version('genro-bag'),
    serializer='Bag.to_xml(legacy_mode=True, catalog=GnrClassCatalog())',
    sources={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
    fixtures={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.glob('*.xml'))},
)
(target / 'provenance.json').write_text(json.dumps(metadata, indent=2) + '\n')
print('Frozen rows.xml, empty.xml and provenance.json from existing Bag serializer')
