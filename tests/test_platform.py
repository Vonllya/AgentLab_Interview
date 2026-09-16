import json
import time
from unittest.mock import patch
import pytest
from backend import storage as s, workspace as w, agent, runs
from backend.executor import docker_command


def test_session_isolation_boundaries_restore(client,session):
    other=client.post('/api/sessions',json={'task_id':'rag'}).json()
    original=client.get('/api/sessions/'+session['id']).json()['code']
    result=client.put('/api/sessions/'+session['id']+'/files',json={'code':'# changed','diagnosis':'定位说明'})
    assert result.status_code==200
    restored=client.get('/api/sessions/'+session['id']).json()
    assert restored['code']=='# changed' and restored['diagnosis']=='定位说明'
    assert client.get('/api/sessions/'+other['id']).json()['code']==original
    for path in ['../private/reference.py','/etc/passwd','public_test.py','solution.py/../x','solution.py\x00']:
        assert client.get('/api/sessions/'+session['id']+'/files',params={'path':path}).status_code==400
    path=w.safe_file(session,'solution.py'); path.unlink(); path.symlink_to('/etc/passwd')
    assert client.get('/api/sessions/'+session['id']+'/files').status_code==400


def test_no_hidden_routes_and_origin(client,session):
    assert client.get('/api/tasks').status_code==200
    assert 'hints' not in client.get('/api/tasks').text
    assert client.get('/tasks/rag/1.0.0/private/reference.py').status_code==404
    assert client.post('/api/sessions',json={'task_id':'rag'},headers={'origin':'https://evil.example'}).status_code==403
    assert client.get('/api/tasks',headers={'host':'evil.example'}).status_code==403
    assert client.post('/api/sessions',json={'task_id':'../../etc'}).status_code==422


def test_hint_permissions_and_validation(client,session):
    with pytest.raises(ValueError):agent.tool(session,'request_hint',{})
    for name,args in [('read_workspace_file',{'path':'../secret'}),('run_public_tests',{'command':'id'}),('evil',{})]:
        with pytest.raises(ValueError):agent.tool(session,name,args)
    for i in range(3):
        hint=client.post('/api/sessions/'+session['id']+'/hint').json()
        assert hint['level']==i+1
    for _ in range(2):
        rejected=client.post('/api/sessions/'+session['id']+'/hint')
        assert rejected.status_code==400 and rejected.json()['detail']=='已获取全部提示'
    assert len(s.all_objects('hint',session['id']))==3
    assert len([e for e in s.all_objects('event',session['id']) if e.get('hint_id')])==3
    other=w.create('retry')
    id=s.ident();s.put('run',id,{'id':id,'session':other['id']},other['id'])
    with pytest.raises(ValueError):agent.tool(session,'get_run_result',{'run_id':id})


def test_mock_and_model_failure(client,session,monkeypatch):
    assert client.get('/api/health').json()['agent_mode']=='mock'
    reply=client.post('/api/sessions/'+session['id']+'/chat',json={'message':'测试通过了吗？'}).json()
    assert 'Mock' in reply['content'] and reply['mode']=='mock'
    monkeypatch.setenv('AGENT_MODE','real')
    monkeypatch.delenv('MODEL_API_KEY',raising=False)
    reply=agent.chat(session,'检查代码')
    assert reply['status']=='error' and '暂不可用' in reply['content']
    assert client.put('/api/sessions/'+session['id']+'/files',json={'code':'# editable'}).status_code==200


def test_real_adapter_http_is_dynamic(monkeypatch):
    import httpx
    monkeypatch.setenv('MODEL_API_KEY','test-secret')
    def post(self,url,**kwargs):
        assert url.endswith('/chat/completions')
        assert kwargs['json']['messages'][0]['content']=='input'
        return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'动态模型内容'}}]},request=httpx.Request('POST',url))
    monkeypatch.setattr(httpx.Client,'post',post)
    assert agent.completion([{'role':'user','content':'input'}])['content']=='动态模型内容'


def test_agent_budget_repeated_tools_and_error(client,session,monkeypatch):
    monkeypatch.setenv('AGENT_MODE','real')
    count=[]
    def completion(*args):
        count.append(1)
        return {'role':'assistant','tool_calls':[{'id':str(len(count)), 'type':'function','function':{'name':'read_workspace_file','arguments':'{"path":"solution.py"}'}}]}
    monkeypatch.setattr(agent,'completion',completion)
    agent.chat(session,'分析')
    events=s.all_objects('event',session['id'])
    assert len(count)<=agent.MAX_ROUNDS
    assert len([e for e in events if e['role']=='tool'])<=agent.MAX_CALLS
    assert any('重复' in e['content'] for e in events)
    assert len([e for e in events if e['role']=='tool' and e['status']=='ok'])==1


def test_docker_policy_and_disabled(client,session,monkeypatch,tmp_path):
    cmd=docker_command(tmp_path,'test')
    for option in ['--network','--read-only','--user','--cap-drop','--security-opt','--memory','--pids-limit','--cpus']:
        assert option in cmd
    assert '/var/run/docker.sock' not in ' '.join(cmd)
    monkeypatch.setattr(runs,'availability',lambda:(False,'Docker 不可用'))
    assert client.post('/api/sessions/'+session['id']+'/runs').status_code==400
    assert not s.all_objects('run',session['id'])


def test_restart_interrupted(client,session):
    id=s.ident();s.put('run',id,{'id':id,'session':session['id'],'status':'running'},session['id'])
    s.init()
    assert s.get('run',id)['status']=='interrupted'
    assert (s.DATA/'runs'/id/'cancelled').exists()


def test_snapshots_and_constraints(client,session):
    one=w.snapshot(session);w.save(session,w.read(session)+'\n# new','new');two=w.snapshot(session)
    assert one!=two
    assert not (s.DATA/'snapshots'/one/'solution.py').read_text().endswith('# new')
    assert client.get('/api/sessions/'+session['id']+'/snapshots/'+two).status_code==404
    retry=w.create('retry')
    original=w.read(retry)
    assert w.constraints(retry,original+'\nx=1')
    assert not w.constraints(retry,(s.package(retry)/'private/reference.py').read_text())


def test_report_binding_with_stubbed_infrastructure(client,session,monkeypatch):
    # Tests storage/report plumbing only; this stub is NOT code-execution evidence.
    monkeypatch.setattr(runs,'availability',lambda:(True,''))
    class Process:
        def __init__(self,cmd,**kwargs):
            config=json.loads(open(kwargs['env']['AGENTLAB_GRADE_CONFIG']).read())
            with open(config['results'],'w') as out:
                for c in config['cases']:out.write(json.dumps({'id':c['id'],'group':c['group'],'visibility':c['visibility'],'status':'passed','detail':'infrastructure stub'})+'\n')
        def wait(self,timeout=None):return 0
    # Stub only the trusted grader subprocess. Docker cleanup must use real Popen.
    real_popen=runs.subprocess.Popen
    def spawn(cmd,**kwargs):
        if kwargs.get('env',{}).get('AGENTLAB_GRADE_CONFIG'):
            return Process(cmd,**kwargs)
        return real_popen(cmd,**kwargs)
    monkeypatch.setattr(runs.subprocess,'Popen',spawn)
    run=client.post('/api/sessions/'+session['id']+'/submit').json()
    w.save(session,'# later edit','later diagnosis')
    for _ in range(100):
        reports=s.all_objects('report',session['id'])
        if reports:break
        time.sleep(.01)
    assert reports[0]['snapshot']==run['snapshot']
    assert reports[0]['objective']['snapshot']==run['snapshot']
    assert reports[0]['diagnosis']==''
    assert (s.DATA/'snapshots'/run['snapshot']/'solution.py').read_text()!='# later edit'


def test_model_cannot_emit_patch():
    assert '已拦截' in agent.safe_response('```python\ndef answer(): pass\n```')
    assert agent.safe_response('已观察：尚未运行；待验证：空输入。').startswith('已观察')


def test_concurrency_limits(client,session,monkeypatch):
    monkeypatch.setattr(runs,'availability',lambda:(True,''))
    class NoStart:
        def __init__(self,**kwargs):pass
        def start(self):pass
    monkeypatch.setattr(runs.threading,'Thread',NoStart)
    runs.start(session,'public')
    try:
        with pytest.raises(ValueError,match='本会话'):runs.start(session,'public')
        other=w.create('retry');runs.start(other,'public')
        try:
            with pytest.raises(ValueError,match='资源已满'):runs.start(w.create('resume'),'public')
        finally:runs.POOL.release()
    finally:runs.POOL.release()


def test_agent_decides_tool_then_explains_evidence(client,session,monkeypatch):
    monkeypatch.setenv('AGENT_MODE','real')
    messages_seen=[]
    def model(messages,tools=None):
        messages_seen.append(messages.copy())
        if len(messages_seen)==1:
            return {'role':'assistant','tool_calls':[{'id':'call-1','type':'function','function':{'name':'get_task_brief','arguments':'{}'}}]}
        observed=json.loads(messages[-1]['content'])
        assert observed['result']['id']=='rag'
        return {'content':'已观察：题面要求保留排列能力。证据 '+observed['evidence_id']+'。待验证：请运行公开测试。'}
    monkeypatch.setattr(agent,'completion',model)
    result=agent.chat(session,'题面要求什么？')
    assert len(messages_seen)==2 and '已观察' in result['content']
    tool_event=next(e for e in s.all_objects('event',session['id']) if e['role']=='tool')
    assert tool_event['id'] in result['content']


def test_agent_over_budget_has_no_side_effects(client,session,monkeypatch):
    monkeypatch.setenv('AGENT_MODE','real')
    monkeypatch.setattr(agent,'completion',lambda *args:{'tool_calls':[{'id':str(i),'function':{'name':'request_hint','arguments':'{}'}} for i in range(7)]})
    result=agent.chat(session,'给我所有提示')
    assert result['status']=='error' and result['error']['category']=='tool_budget'
    assert not s.all_objects('hint',session['id'])


def test_hidden_checks_are_sanitized(client,session,monkeypatch):
    # Real grading logic with a trusted transport fixture, no task code import.
    import os
    import subprocess
    import sys
    config=s.DATA/'sanitize.json';result=s.DATA/'sanitized.jsonl'
    config.write_text(json.dumps({'snapshot_dir':'/does-not-exist','results':str(result),'cases':[{'id':'opaque-check','group':'target','visibility':'hidden','input':{'secret':'hidden fixture marker'},'expected':'do not expose'}]}))
    env=os.environ.copy();env['AGENTLAB_GRADE_CONFIG']=str(config)
    completed=subprocess.run([sys.executable,'-m','pytest','backend/grade_suite.py','-q','--tb=no'],env=env,capture_output=True,timeout=15)
    assert completed.returncode==1
    visible=json.loads(result.read_text())
    assert visible['status']=='error'
    assert 'hidden fixture marker' not in json.dumps(visible)
    assert 'do not expose' not in json.dumps(visible)


def test_cancelled_grader_never_starts_a_container(client,tmp_path):
    import os
    import subprocess
    import sys
    cancel=tmp_path/'cancelled';cancel.touch()
    checks=tmp_path/'checks.jsonl';config=tmp_path/'grade.json'
    config.write_text(json.dumps({'snapshot_dir':'/intentionally-missing','cancel_file':str(cancel),'results':str(checks),
        'cases':[{'id':'cancelled-case','group':'target','visibility':'hidden','input':{},'expected':{}}]}))
    result=subprocess.run([sys.executable,'-m','pytest','backend/grade_suite.py','-q','--tb=no'],
        env=dict(os.environ,AGENTLAB_GRADE_CONFIG=str(config)),capture_output=True,timeout=15)
    assert result.returncode==1
    evidence=json.loads(checks.read_text())
    assert evidence['status']=='error'
    assert evidence['detail']=='原执行已取消，不再启动容器'


@pytest.mark.parametrize('check_status,exit_code,expected',[('error',1,'error'),('timeout',1,'timeout'),('failed',1,'failed'),('failed',0,'failed')])
def test_run_terminal_status_from_trusted_checks(client,session,monkeypatch,check_status,exit_code,expected):
    # Transport stub: status handling only, never counts as Docker verification.
    monkeypatch.setattr(runs,'availability',lambda:(True,''))
    class Process:
        def __init__(self,cmd,**kwargs):
            config=json.loads(open(kwargs['env']['AGENTLAB_GRADE_CONFIG']).read())
            with open(config['results'],'w') as out:
                for case in config['cases']:
                    out.write(json.dumps(dict(id=case['id'],group=case['group'],visibility=case['visibility'],status=check_status,detail='trusted fixture'))+'\n')
        def wait(self,timeout=None):return exit_code
    # Stub only the trusted grader subprocess. Docker cleanup must use real Popen.
    real_popen=runs.subprocess.Popen
    def spawn(cmd,**kwargs):
        if kwargs.get('env',{}).get('AGENTLAB_GRADE_CONFIG'):
            return Process(cmd,**kwargs)
        return real_popen(cmd,**kwargs)
    monkeypatch.setattr(runs.subprocess,'Popen',spawn)
    run=client.post('/api/sessions/'+session['id']+'/runs').json()
    for _ in range(200):
        current=s.get('run',run['id'])
        if current['status'] not in ('queued','running'):break
        time.sleep(.01)
    assert current['status']==expected
