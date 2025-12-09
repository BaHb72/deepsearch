import os
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(os.getcwd())
sys.path.insert(0, str(project_root))

os.environ["APP__ENV"] = "dev"

try:
    from deepsearch.config import get_config
    settings = get_config()
    print(f"DEBUG: database.cache.password = '{settings.database.cache.password}'")
    print(f"DEBUG: database.cache.username = '{settings.database.cache.username}'")
    print(f"DEBUG: database.cache.host = '{settings.database.cache.host}'")
    print(f"DEBUG: database.cache.port = '{settings.database.cache.port}'")
except Exception as e:
    print(f"ERROR: {e}")
