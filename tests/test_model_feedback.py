import json
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from backend import agent, storage as s, workspace as w


def report_for(session):
    hint=agent.hint(session)
    snapshot=w.snapshot(session)
    run={'id':s.ident(),'snapshot':snapshot,'checks':[{'id':'mapping','status':'passed'}],'hints':[hint]}
    return dict(id=s.ident(),session=session['id'],run_id=run['id'],snapshot=snapshot,objective=run,diagnosis='提交时诊断')


@pytest.mark.parametrize('content', ['可显示正文',[{'type':'text','text':'可显示正文'}]])
def test_adapter_visible_content_and_reasoning_budget(monkeypatch,content):
    monkeypatch.setenv('MODEL_API_KEY','private-key')
    def post(self,url,**kwargs):
        assert kwargs['json']['max_tokens']==4096
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':content,'reasoning_content':'never persist'}}]},request=httpx.Request('POST',url))
    monkeypatch.setattr(httpx.Client,'post',post)
    assert agent.completion([])['content']=='可显示正文'


@pytest.mark.parametrize('choice,category', [
    ({'finish_reason':'length','message':{'content':'','reasoning_content':'secret reasoning'}},'output_limit'),
    ({'finish_reason':'stop','message':{'content':''}},'empty_content'),
    ({'message':{'content':{'unexpected':'value'}}},'response_format'),
])
def test_adapter_empty_or_truncated_not_success(monkeypatch,choice,category):
    monkeypatch.setenv('MODEL_API_KEY','private-key')
    monkeypatch.setattr(httpx.Client,'post',lambda self,url,**kw:httpx.Response(200,json={'choices':[choice]},request=httpx.Request('POST',url)))
    with pytest.raises(agent.ModelFailure) as error:agent.completion([])
    assert error.value.category==category
    assert 'secret reasoning' not in str(error.value)


def test_report_generation_persistence_and_submission_snapshot(client,session,monkeypatch):
    monkeypatch.setenv('AGENT_MODE','real')
    report=report_for(session)
    expected=json.loads(json.dumps(report))
    w.save(session,w.read(session)+'\n# later code','later diagnosis')
    agent.hint(session); agent.hint(session)
    def completion(messages,**kwargs):
        pending=client.get('/api/reports/'+report['id']).json()
        assert pending['feedback_status']=='generating'
        evidence=json.loads(messages[-1]['content'])
        assert evidence['snapshot']==expected['snapshot']
        assert evidence['diagnosis']=='提交时诊断'
        assert '# later code' not in evidence['diff']
        return {'content':'依据执行 '+report['run_id']+'：需要更多定位依据。','_meta':{'finish_reason':'stop'},'reasoning_content':'never store'}
    monkeypatch.setattr(agent,'completion',completion)
    agent.report_feedback(session,report)
    persisted=client.get('/api/reports/'+report['id']).json()
    assert persisted['feedback_status']=='generated'
    assert report['run_id'] in persisted['feedback']
    assert persisted['objective']==expected['objective']
    assert persisted['snapshot']==expected['snapshot']
    assert len(persisted['objective']['hints'])==1
    assert 'never store' not in json.dumps(persisted)
    s.init()
    assert s.get('report',report['id'])==persisted


@pytest.mark.parametrize('error,category', [
    (agent.ModelFailure('output_limit','模型输出预算耗尽'),'output_limit'),
    (httpx.ReadTimeout('secret URL and key'),'timeout'),
    (httpx.HTTPStatusError('secret response',request=httpx.Request('POST','https://secret.invalid'),response=httpx.Response(429)),'rate_limit'),
    (RuntimeError('secret implementation details'),'internal'),
])
def test_report_failure_preserves_objective_and_safe_reason(client,session,monkeypatch,error,category):
    monkeypatch.setenv('AGENT_MODE','real')
    report=report_for(session); objective=json.loads(json.dumps(report['objective']))
    def fail(*args,**kwargs):raise error
    monkeypatch.setattr(agent,'completion',fail)
    agent.report_feedback(session,report)
    restored=client.get('/api/reports/'+report['id']).json()
    assert restored['feedback_status']=='failed'
    assert restored['feedback_error']['category']==category
    assert restored['objective']==objective
    assert 'secret' not in json.dumps(restored)


def test_pending_feedback_restart_is_terminal(client,session):
    report=report_for(session); report['feedback_status']='generating'
    s.put('report',report['id'],report,session['id'])
    s.init()
    restored=s.get('report',report['id'])
    assert restored['feedback_status']=='failed'
    assert restored['feedback_error']['category']=='interrupted'
    assert restored['objective']==report['objective']


def test_concurrent_l3_requests_only_record_once(client,session):
    agent.hint(session); agent.hint(session)
    def request():
        try:return agent.hint(session)['level']
        except ValueError:return 'capped'
    with ThreadPoolExecutor(max_workers=4) as pool:result=list(pool.map(lambda _:request(),range(4)))
    assert result.count(3)==1 and result.count('capped')==3
    assert len(s.all_objects('hint',session['id']))==3


def test_real_chat_tool_results_and_hint_denial(client,session,monkeypatch):
    monkeypatch.setenv('AGENT_MODE','real')
    count=[]
    def completion(messages,tools):
        count.append(1)
        if len(count)==1:
            return {'content':'','reasoning_content':'ephemeral only','tool_calls':[
                {'id':'read','type':'function','function':{'name':'read_workspace_file','arguments':'{"path":"solution.py"}'}},
                {'id':'hint','type':'function','function':{'name':'request_hint','arguments':'{}'}}]}
        assert messages[-3]['reasoning_content']=='ephemeral only'
        assert json.loads(messages[-2]['content'])['result']==w.read(session)
        denial=json.loads(messages[-1]['content'])
        assert '提示未授权' in denial['result']['error']
        return {'content':'已观察保存代码；尚需测试证据。'}
    monkeypatch.setattr(agent,'completion',completion)
    reply=client.post('/api/sessions/'+session['id']+'/chat',json={'message':'请检查代码'}).json()
    assert reply['mode']=='real' and '已观察' in reply['content']
    assert len(count)==2 and not s.all_objects('hint',session['id'])
    assert 'ephemeral only' not in json.dumps(s.all_objects('event',session['id']))


def test_tool_budget_reserves_evidence_based_final_reply(client,session,monkeypatch):
    monkeypatch.setenv('AGENT_MODE','real')
    count=[]
    def completion(messages,tools):
        count.append(1)
        if tools is None:
            assert any(m['role']=='tool' for m in messages)
            return {'content':'已观察保存代码；本轮没有测试结果，仍待验证。'}
        return {'tool_calls':[{'id':str(len(count)),'type':'function','function':{'name':'get_session_evidence','arguments':'{}'}}]}
    monkeypatch.setattr(agent,'completion',completion)
    reply=agent.chat(session,'检查代码和测试')
    assert '已观察' in reply['content'] and '预算已耗尽' not in reply['content']
    assert len(count)==agent.MAX_ROUNDS
