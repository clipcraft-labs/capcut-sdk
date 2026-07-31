"""Allow ``python -m capcut_sdk`` to behave like the ``capcut`` command."""

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())

