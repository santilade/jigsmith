"""Entry point: `python -m tui`."""
from tui.app import JigsmithApp


def main() -> None:
    JigsmithApp().run()


if __name__ == "__main__":
    main()
