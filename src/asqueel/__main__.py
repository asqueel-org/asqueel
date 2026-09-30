"""python -m asqueel uses the same entry point as the installed command."""
from .cli import main

if __name__ == '__main__':
    raise SystemExit(main())
