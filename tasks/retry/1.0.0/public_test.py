"""可信宿主测试：execute 必须是 Docker RPC，不得导入工作区代码。"""
import json
from pathlib import Path
import pytest

CASES = json.loads(Path(__file__).with_name("public_cases.json").read_text())

@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_behavior(case, execute):
    assert execute(case["input"]) == case["expected"]
