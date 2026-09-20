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
        actual=execute(Path(CONFIG['snapshot_dir']),case['input'],allowed_files=CONFIG.get('allowed_files'),image_id=CONFIG.get('image_id'))
        if case.get('contract')=='generated_json':
            from backend.generation_schema import conforms
            if isinstance(actual,dict) and 'error' in actual or not conforms(actual,case['output_schema']):
                raise ValueError('生成任务运行错误或输出协议无效')
            result['trust']='模型生成结构化期望，经作者审核；由平台解释器判定'
            if case.get('repeat_count')==2:
                if CONFIG.get('cancel_file') and Path(CONFIG['cancel_file']).exists():raise InterruptedError('原执行已取消')
                again=execute(Path(CONFIG['snapshot_dir']),case['input'],allowed_files=CONFIG.get('allowed_files'),image_id=CONFIG.get('image_id'))
                if isinstance(again,dict) and 'error' in again or not conforms(again,case['output_schema']):raise ValueError('重复执行运行错误或输出协议无效')
                result.update(repeat_count=2,repeat_consistent=json.dumps(actual,sort_keys=True)==json.dumps(again,sort_keys=True))
                assert result['repeat_consistent'], '重复执行结果不一致'
        if case.get('contract')=='versioned_index':
            if not isinstance(actual,dict) or 'result' not in actual:
                raise ValueError('任务输出结构错误，不计为预设故障')
            if case['visibility']=='public':
                trace=json.dumps(actual.get('trace'),ensure_ascii=False)
                result['diagnostic_trace']={'source':'user_code','warning':'辅助调查；用户代码可修改，不能作为独立通过证明','events':actual.get('trace') if len(trace)<12000 else None,'truncated':len(trace)>=12000}
            actual=actual['result']
        result['category']='behavior'
        if case.get('coverage'): result['coverage']=case['coverage']
        assert actual==case['expected']
        result.update(status='passed',detail='行为契约通过')
    except AssertionError:
        result.update(status='failed',detail='行为与题面契约不一致')
        if result.get('repeat_consistent') is False:
            result['detail']='同一输入两次独立执行结果不一致'
        elif case['visibility']=='public':
            result['detail']=f"期望 {case['expected']!r}，实际 {actual!r}"[:4000]
        raise
    except Exception as exc:
        result.update(status='timeout' if isinstance(exc,TimeoutError) else 'error',detail=str(exc)[:500])
        raise
    finally:
        result['duration']=round(time.monotonic()-started,3)
        with Path(CONFIG['results']).open('a') as stream:
            stream.write(json.dumps(result,ensure_ascii=False)+'\n')
