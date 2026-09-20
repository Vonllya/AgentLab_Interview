"""运行方式见 README；用户模块始终在 Docker 中加载，轨迹不判分。"""
import json
from pathlib import Path
import pytest

CASES = json.loads(Path(__file__).with_name('public_cases.json').read_text())

@pytest.mark.parametrize('case', CASES, ids=lambda c: c['id'])
def test_public(case, execute):
    assert execute(case['input'])['result'] == case['expected']
