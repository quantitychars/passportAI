"""pytest configuration for PassportAI tests.

This file ensures the project root is in sys.path so that relative imports
like 'from src.core.pipeline import ...' work correctly.
"""

import sys
from pathlib import Path

# Add the project root to sys.path so pytest can find src/ modules
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
