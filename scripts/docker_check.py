"""Read-only Docker preflight; never prints environment values or provider keys."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.executor import diagnose

result = diagnose()
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result['status'] == 'ready' else 2)
