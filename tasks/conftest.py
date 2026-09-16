"""Optional direct execution of the published pytest files, using Docker only."""
from pathlib import Path
import pytest
from backend.executor import execute as docker_execute, availability


def pytest_addoption(parser):
    parser.addoption('--workspace-snapshot',help='仅含 solution.py 的已保存快照目录')

@pytest.fixture
def execute(request):
    folder=request.config.getoption('--workspace-snapshot')
    if not folder:pytest.fail('请提供 --workspace-snapshot；禁止在宿主导入用户代码')
    ready,reason=availability()
    if not ready:pytest.skip(reason)
    return lambda payload:docker_execute(Path(folder),payload)
