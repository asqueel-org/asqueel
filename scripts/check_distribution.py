"""Validate Asqueel artifacts before upload."""
import sys
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path

for filename in sys.argv[1:]:
    path = Path(filename)
    if path.suffix == '.whl':
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            raw = archive.read(next(n for n in names if n.endswith('.dist-info/METADATA')))
    else:
        with tarfile.open(path) as archive:
            names = archive.getnames()
            raw = archive.extractfile(next(n for n in names if n.endswith('/PKG-INFO'))).read()
    metadata = BytesParser().parsebytes(raw)
    assert metadata['Name'] == 'asqueel'
    assert not any('genro_sql/' in n for n in names)
    for required in ('__init__.py', 'py.typed'):
        assert any(('/' + n).endswith('/asqueel/' + required) for n in names), required
    if path.suffix == '.whl':
        assert 'asqueel/grammar.md' in names
    assert not any(' @ ' in r for r in metadata.get_all('Requires-Dist', []))
    print(f'{path.name}: package identity and contents OK')
