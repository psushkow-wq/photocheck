import sys
import os
from pathlib import Path

# Add project root to path
root = Path(__file__).parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "photocheck"))

# Set up engine path
os.environ.setdefault("ENGINE_PATH", str(root))

from photocheck.app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
