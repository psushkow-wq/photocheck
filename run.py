import sys
import os
from pathlib import Path

root = Path(__file__).parent
sys.path.insert(0, str(root))

from flask import Flask
import photocheck.app as photocheck_app

# Fix template and static folders
photocheck_app.app.template_folder = str(root / "photocheck" / "templates")
photocheck_app.app.static_folder = str(root / "photocheck" / "static")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    photocheck_app.app.run(host="0.0.0.0", port=port, debug=False)
