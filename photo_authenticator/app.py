"""
app.py — Entry point for Photo Authenticator.

Run with:
    python app.py
"""

import sys
from pathlib import Path

# Ensure project root is on the import path when running directly
sys.path.insert(0, str(Path(__file__).parent))

from config import setup_logging
setup_logging()

from ui.main_window import MainWindow


def main() -> None:
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
