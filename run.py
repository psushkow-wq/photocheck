import sys
import os
from pathlib import Path

root = Path(__file__).parent
sys.path.insert(0, str(root))

# Set template folder explicitly before importing
os.chdir(str(root / "photocheck"))

from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
