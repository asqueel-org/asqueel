"""Local configuration cards, following Kajenn's named-site registry convention."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re


class RegistrationError(ValueError):
    """Invalid or unavailable local registration, without configuration values."""


class DatabaseRegistry:
    """One path-only card per name under ASQUEEL_HOME/databases."""

    def __init__(self, home: str | Path | None = None):
        self.home = Path(home or os.environ.get('ASQUEEL_HOME') or '~/.asqueel').expanduser()
        self.directory = self.home / 'databases'

    def card_path(self, name: str) -> Path:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', name):
            raise RegistrationError('Registry names use letters, digits, underscores and hyphens')
        return self.directory / f'{name}.json'

    def register(self, name: str, folder: str | Path) -> Path:
        path = self.card_path(name)
        folder = Path(folder).expanduser().resolve()
        if not (folder / 'configure.py').is_file():
            raise RegistrationError('The registered folder must contain configure.py')
        self.directory.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents accidental replacement of another registration.
        try:
            stream = path.open('x', encoding='utf-8')
        except FileExistsError:
            raise RegistrationError(f'{name} is already registered; unregister it before replacing it') from None
        with stream:
            json.dump({'folder': str(folder)}, stream, indent=2)
            stream.write('\n')
        return path

    def resolve(self, name: str) -> Path:
        path = self.card_path(name)
        if not path.is_file():
            raise RegistrationError(f'Unknown registered database: {name}')
        card = json.loads(path.read_text(encoding='utf-8'))
        folder = Path(card['folder'])
        if not folder.is_absolute():
            raise RegistrationError('Registered database folders must be absolute paths')
        source = folder / 'configure.py'
        if not source.is_file():
            raise RegistrationError(f'Registered database {name} has no configure.py')
        return source

    def names(self) -> list[str]:
        return sorted(path.stem for path in self.directory.glob('*.json'))

    def remove(self, name: str) -> None:
        """Remove only the card, never the source folder or database."""
        try:
            self.card_path(name).unlink()
        except FileNotFoundError:
            raise RegistrationError(f'Unknown registered database: {name}') from None
