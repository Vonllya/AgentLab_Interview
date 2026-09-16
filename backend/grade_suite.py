"""Only trusted code runs in this host pytest process."""
import json
import os
import time
from pathlib import Path
import pytest
from backend.executor import execute

CONFIG=json.loads(Path(os.environ['AGENTLAB_GRADE_CONFIG']).read_text())

@pytest.mark.parametrize('case', CONFIG['cases'], ids=lambda c:c['id'])
def test_behavior(case):
    started=time.monotonic()
    result={'id':case['id'],'group':case['group'],'visibility':case['visibility']}
    try:
        if CONFIG.get('cancel_file') and Path(CONFIG['cancel_file']).exists():
            raise InterruptedError('原执行已取消，不再启动容器')
        actual=execute(Path(CONFIG['snapshot_dir']),case['input'])
        assert actual==case['expected']
        result.update(status='passed',detail='行为契约通过')
    except AssertionError:
        result.update(status='failed',detail='行为与题面契约不一致')
        if case['visibility']=='public':
            result['detail']=f"期望 {case['expected']!r}，实际 {actual!r}"[:4000]
        raise
    except Exception as exc:
        result.update(status='timeout' if isinstance(exc,TimeoutError) else 'error',detail=str(exc)[:500])
        raise
    finally:
        result['duration']=round(time.monotonic()-started,3)
        with Path(CONFIG['results']).open('a') as stream:
            stream.write(json.dumps(result,ensure_ascii=False)+'\n')
