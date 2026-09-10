import sys
from pathlib import Path

# Allow running pytest from the python/ directory without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
