"""Untrusted program entry point; grading happens outside this container."""
import importlib.util
import json
import sys

try:
    spec = importlib.util.spec_from_file_location('solution', '/workspace/solution.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    request = json.loads(sys.stdin.read(65536))
    result = module.scenario(request)
except Exception as exc:
    result = {'error': type(exc).__name__}
print(json.dumps(result, ensure_ascii=False))
