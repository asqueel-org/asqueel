"""Package folders written by tests: the only entry for a table's ``Table`` class."""
import textwrap


def write_layout(folder, **tables):
    """Write ``folder`` with an empty ``main.py`` and one ``model/<table>.py`` per source; return its path."""
    (folder / 'model').mkdir(parents=True)
    (folder / 'main.py').write_text('class Package:\n    pass\n')
    for name, source in tables.items():
        (folder / 'model' / f'{name}.py').write_text(textwrap.dedent(source))
    return str(folder)
