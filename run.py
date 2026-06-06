import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from photocheck.app import app

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
