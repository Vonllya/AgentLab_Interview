"""Real user code is NEVER imported by this test process."""
import json
import time
from pathlib import Path
import pytest
from backend import executor, storage as s, workspace as w

pytestmark=pytest.mark.skipif(not executor.availability()[0],reason=executor.availability()[1])


def cases(task):
    p=s.TASKS/task/'1.0.0'
    return json.loads((p/'public_cases.json').read_text())+json.loads((p/'private/hidden_cases.json').read_text())

@pytest.mark.parametrize('task',['rag','retry','resume'])
@pytest.mark.parametrize('version',['initial/solution.py','private/normal.py','private/reference.py'])
def test_task_versions(tmp_path,task,version,record_property):
    tmp_path.chmod(0o755)
    (tmp_path/'solution.py').write_text((s.TASKS/task/'1.0.0'/version).read_text())
    observations=[]
    for case in cases(task):
        actual=executor.execute(tmp_path,case['input'])
        assert not (isinstance(actual,dict) and 'error' in actual) or actual==case['expected'], '意外程序错误，不能作为预设故障命中的证据'
        observations.append(dict(id=case['id'],group=case['group'],actual=actual,expected=case['expected'],passed=actual==case['expected']))
    record_property('matrix',json.dumps(observations,ensure_ascii=False))
    if version.startswith('initial'):
        assert all(o['passed'] for o in observations if o['group']=='regression')
        failing=[o for o in observations if o['group']=='target' and not o['passed']]
        assert failing
        if task=='rag':
            assert any([d['text'] for d in o['actual']]==[d['text'] for d in o['expected']] and
                       [d['citation'] for d in o['actual']]!=[d['citation'] for d in o['expected']] for o in failing)
        elif task=='retry':
            assert any(len(o['actual']['records'])>len(o['expected']['records']) for o in failing)
        else:
            assert any(any(len(log)>len(set(log)) for log in o['actual'].values()) for o in failing)
        target=next(c for c in cases(task) if c['id']==failing[0]['id'])
        assert executor.execute(tmp_path,target['input'])==failing[0]['actual'], '故障必须在重复执行中稳定复现'
    else:
        assert all(o['passed'] for o in observations)

@pytest.mark.parametrize('task',['rag','retry','resume'])
def test_evasion(tmp_path,task):
    ref=(s.TASKS/task/'1.0.0/private/reference.py').read_text()
    if task=='rag':ref=ref.replace('selected = [documents[i] for i in order]','selected = documents')
    elif task=='retry':ref=ref.replace('range(attempts)','range(1)').replace('if attempt == attempts - 1:','if True:')
    else:ref=ref.replace('    completed = json.loads', '    if state_file.exists():\n        return json.loads(state_file.read_text())\n    completed = json.loads')
    tmp_path.chmod(0o755)
    (tmp_path/'solution.py').write_text(ref)
    # A normal request must work before interpreting target failure as evasion.
    normal=next(c for c in cases(task) if c['group']=='regression')
    if task=='rag':
        docs=normal['input']['documents']
        normal={'input':{'documents':docs,'order':list(range(len(docs)))},'expected':[{'text':d['text'],'citation':d['id']} for d in docs]}
    assert executor.execute(tmp_path,normal['input'])==normal['expected']
    observed=[(c,executor.execute(tmp_path,c['input'])) for c in cases(task) if c['group']=='target']
    assert all(not isinstance(actual,dict) or 'error' not in actual or (task=='retry' and actual=={'error':'TransientError'}) for _,actual in observed)
    assert any(actual!=case['expected'] for case,actual in observed)


def test_actual_infinite_loop(tmp_path):
    tmp_path.chmod(0o755)
    (tmp_path/'solution.py').write_text('while True: pass')
    with pytest.raises(TimeoutError):executor.execute(tmp_path,{},timeout=1)


def test_e2e_real_execution(client,record_property):
    obj=client.post('/api/sessions',json={'task_id':'rag'}).json();id=obj['id']
    ref=(s.TASKS/'rag/1.0.0/private/reference.py').read_text()
    assert client.put(f'/api/sessions/{id}/files',json={'code':ref,'diagnosis':'根据重排后的文档绑定引用，覆盖过滤与空集。'}).status_code==200
    def wait(run):
        for _ in range(600):
            value=client.get('/api/runs/'+run['id']).json()
            if value['status'] not in ('queued','running'):return value
            time.sleep(.2)
        pytest.fail('run remained pending')
    public=wait(client.post(f'/api/sessions/{id}/runs').json());assert public['status']=='passed'
    assert client.post(f'/api/sessions/{id}/hint').json()['level']==1
    assert client.post(f'/api/sessions/{id}/chat',json={'message':'查看测试证据'}).status_code==200
    submitted_code=ref+'\n# new submission snapshot\n'
    client.put(f'/api/sessions/{id}/files',json={'code':submitted_code,'diagnosis':'提交版本 B'})
    pending=client.post(f'/api/sessions/{id}/submit').json()
    client.put(f'/api/sessions/{id}/files',json={'code':'# later edit','diagnosis':'提交之后的工作副本'})
    submission=wait(pending);assert submission['status']=='passed'
    for _ in range(50):
        restored=client.get('/api/sessions/'+id).json()
        if restored['reports']:break
        time.sleep(.1)
    report=restored['reports'][0]
    assert report['snapshot']==submission['snapshot']!=public['snapshot']
    assert report['run_id']==submission['id']!=public['id']
    assert report['diagnosis']=='提交版本 B'
    snapshot=client.get(f'/api/sessions/{id}/snapshots/'+report['snapshot']).json()
    assert snapshot['code']==submitted_code
    record_property('submission_evidence',json.dumps({'public':public,'submission':submission,'report':report},ensure_ascii=False))
    assert report['objective']['hints'][0]['level']==1
    assert restored['code']=='# later edit'


def containers(run_id):
    import subprocess
    result=subprocess.run(['docker','ps','-aq','--filter','label=agentlab.run='+run_id],capture_output=True,text=True,timeout=5,check=True)
    return result.stdout.splitlines()


@pytest.fixture(autouse=True)
def container_cleanup(monkeypatch):
    run_id=s.ident()
    monkeypatch.setenv('AGENTLAB_RUN_ID',run_id)
    yield
    executor.cleanup_run(run_id)
    assert not containers(run_id), '本用例的容器未清理'


def test_container_abnormal_exit(tmp_path):
    tmp_path.chmod(0o755)
    (tmp_path/'solution.py').write_text('import os\nos._exit(7)\n')
    with pytest.raises(RuntimeError,match='容器异常退出 7'):
        executor.execute(tmp_path,{})


@pytest.mark.parametrize('code,expected',[
    ('while True: pass\n','timeout'),
    ('import os\nos._exit(7)\n','error'),
])
def test_run_failure_terminal_and_cleanup(client,code,expected):
    obj=client.post('/api/sessions',json={'task_id':'rag'}).json()
    client.put('/api/sessions/'+obj['id']+'/files',json={'code':code})
    response=client.post('/api/sessions/'+obj['id']+'/runs')
    assert response.status_code==200
    run=response.json()
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        current=client.get('/api/runs/'+run['id']).json()
        if current['status'] not in ('queued','running'):break
        time.sleep(.1)
    assert current['status']==expected
    assert any(c['status']==expected for c in current['checks'])
    assert not containers(run['id'])


def test_real_backend_restart_interrupts_running_container(tmp_path,record_property):
    """Kill a real API process while an actual Docker workload is active."""
    import os
    import socket
    import subprocess
    import sys
    import httpx
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    data=tmp_path/'server-data';data.mkdir()
    env=dict(os.environ,AGENTLAB_DATA=str(data),AGENT_MODE='mock')
    env.pop('MODEL_API_KEY',None)
    process=None;run=None
    log=(tmp_path/'backend.log').open('w')
    def start():
        process=subprocess.Popen([sys.executable,'-m','uvicorn','backend.app:app','--host','127.0.0.1','--port',str(port)],cwd=s.ROOT,env=env,stdout=log,stderr=log)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            try:
                if http.get('/api/tasks').status_code==200:return process
            except httpx.HTTPError:pass
            if process.poll() is not None:pytest.fail('后端启动失败；不属于题目故障')
            time.sleep(.1)
        process.kill();process.wait();pytest.fail('后端启动超时')
    with httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=10) as http:
        try:
            process=start()
            session=http.post('/api/sessions',json={'task_id':'rag'}).json()
            http.put('/api/sessions/'+session['id']+'/files',json={'code':'while True: pass\n'})
            response=http.post('/api/sessions/'+session['id']+'/runs');assert response.status_code==200
            run=response.json()
            deadline=time.monotonic()+7
            while time.monotonic()<deadline and not containers(run['id']):time.sleep(.1)
            assert containers(run['id']), '必须先观察到真实容器运行，不能用 seeded running 冒充'
            process.kill();process.wait(timeout=5)
            process=start()
            restored=http.get('/api/runs/'+run['id']).json()
            assert restored['status']=='interrupted'
            assert (data/'runs'/run['id']/'cancelled').exists()
            # Observe beyond one per-case deadline to catch an orphan grader starting the next case.
            for _ in range(90):
                assert not containers(run['id'])
                time.sleep(.1)
            assert http.get('/api/sessions/'+session['id']).json()['runs'][0]['status']=='interrupted'
            record_property('restart_evidence',json.dumps(restored,ensure_ascii=False))
        finally:
            if process and process.poll() is None:process.terminate();process.wait(timeout=10)
            if run:executor.cleanup_run(run['id'])
            log.close()
