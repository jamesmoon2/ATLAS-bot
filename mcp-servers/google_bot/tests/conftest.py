from __future__ import annotations

import sys
from pathlib import Path

GOOGLE_BOT_ROOT = Path(__file__).resolve().parents[1]
if str(GOOGLE_BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(GOOGLE_BOT_ROOT))
