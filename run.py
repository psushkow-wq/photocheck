import sys
import os
from pathlib import Path

root = Path(__file__).parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "photocheck"))

# Now import directly
exec(open(root / "photocheck" / "app.py").read())
