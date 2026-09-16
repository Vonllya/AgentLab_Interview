import copy
import json
import threading
import httpx
import pytest
from backend import agent, evidence, storage as s, workspace as w
from test_model_feedback import report_for


@pytest.mark.parametrize('last_failure',[False,True])
def test_output_limit_one_retry_frozen_evidence(client,session,monkeypatch,last_failure):
    monkeypatch.setenv('AGENT_MODE','real')
    report=report_for(session); before=copy.deepcopy(report)
    seen=[]
    def model(messages,**kwargs):
        seen.append((messages,kwargs))
        if len(seen)==1:
            w.save(session,'# later workspace','changed diagnosis');agent.hint(session)
            raise agent.ModelFailure('output_limit','预算耗尽',{'finish_reason':'length'})
        if last_failure:raise agent.ModelFailure('output_limit','仍然耗尽',{'finish_reason':'length'})
        return {'content':'定位依据不足；请补充对应执行的回归说明。','_meta':{'finish_reason':'stop'}}
    monkeypatch.setattr(agent,'completion',model)
    agent.report_feedback(session,report)
    assert len(seen)==2
    assert seen[0][1]['retry'] is False and seen[1][1]['retry'] is True
    assert len(seen[1][0][-1]['content'])<len(seen[0][0][-1]['content'])
    for messages,_ in seen:
        data=json.loads(messages[-1]['content'])
        assert data['snapshot']==before['snapshot'] and data['diagnosis']==before['diagnosis']
        assert '# later workspace' not in data['diff'] and len(data['hint_records'])==1
    restored=s.get('report',report['id'])
    assert restored['objective']==before['objective']
    assert restored['feedback_status']==('failed' if last_failure else 'generated')
    assert len(restored['feedback_attempts'])==2


@pytest.mark.parametrize('category',['empty_content','response_format','timeout'])
def test_non_limit_failure_not_retried(client,session,monkeypatch,category):
    monkeypatch.setenv('AGENT_MODE','real');calls=[]
    def model(*args,**kwargs):
        calls.append(1);raise agent.ModelFailure(category,'失败原因')
    monkeypatch.setattr(agent,'completion',model)
    report=report_for(session);agent.report_feedback(session,report)
    assert len(calls)==1 and report['feedback_status']=='failed'


def test_report_wait_deadline_discards_late_response(client,session,monkeypatch):
    monkeypatch.setenv('AGENT_MODE','real');monkeypatch.setattr(agent,'REPORT_REQUEST_TIMEOUT',.02)
    release=threading.Event();done=threading.Event()
    def model(*args,**kwargs):
        release.wait(2);done.set();return {'content':'late'}
    monkeypatch.setattr(agent,'completion',model)
    report=report_for(session);agent.report_feedback(session,report)
    persisted=s.get('report',report['id'])
    assert persisted['feedback_status']=='failed' and persisted['feedback_error']['category']=='timeout'
    assert persisted['feedback_attempts'][0]['metadata']['content_empty'] is None
    assert persisted['feedback_attempts'][0]['metadata']['parse_status']=='unknown'
    release.set();assert done.wait(1)
    assert s.get('report',report['id'])==persisted


def test_provider_report_parameters_and_unknown_diagnostics(monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY','secret');monkeypatch.setenv('MODEL_BASE_URL','https://api.deepseek.com/v1');monkeypatch.setenv('MODEL_NAME','deepseek-v4-flash')
    def post(self,url,**kwargs):
        assert kwargs['json']['thinking']=={'type':'disabled'}
        assert kwargs['json']['max_tokens']==1200
        return httpx.Response(200,json={'choices':[{'message':{'content':'简短正文'}}]},request=httpx.Request('POST',url))
    monkeypatch.setattr(httpx.Client,'post',post)
    meta=agent.completion([{'role':'user','content':'abc'}],purpose='report')['_meta']
    assert meta['input_chars']==3 and meta['usage']['prompt_tokens'] is None
    assert meta['finish_reason'] is None and meta['content_empty'] is False
    assert meta['parse_status']=='parsed' and 'secret' not in json.dumps(meta)
    monkeypatch.setenv('MODEL_BASE_URL','https://other.example/v1')
    assert 'thinking' not in agent.request_options('report')
    assert agent.request_options('report',True)['max_tokens']==1800


def test_scope_not_behavior_and_hidden_unknown(client,session):
    run={'checks':[
        {'id':'modification-scope','group':'constraint','status':'passed','visibility':'public','detail':'old ambiguous claim'},
        {'id':'rag-1','group':'target','status':'failed','visibility':'public'},
        {'id':'secret','group':'target','status':'passed','visibility':'hidden','detail':'SECRET INPUT OR TRACE'},
        {'id':'absent-case','group':'target','status':'passed','visibility':'public'},
    ]}
    result=evidence.run_evidence(session,run);scope,behavior,hidden,unknown=result['checks']
    assert scope['category']=='modification_scope' and '过滤正确' in scope['does_not_prove']
    assert behavior['coverage']['reordered'] and '不能排除' in behavior['supports']
    # Actual public sample is a two-of-four subset, not a full filter matrix.
    assert behavior['coverage']['candidate_count']==4 and behavior['coverage']['selected_count']==2
    assert behavior['coverage']['selected_indices']==[1,0]
    assert behavior['coverage']['selection_shape']=='前缀连续子集'
    assert '未知' in unknown['coverage']['summary'] and '未知' in hidden['coverage']['summary']
    assert 'SECRET' not in json.dumps(result) and 'old ambiguous claim' not in json.dumps(result)
    assert '行为等价' in ' '.join(result['interpretation_limits'])
    assert run['checks'][0]['detail']=='old ambiguous claim'


def test_invalid_envelope_has_parse_audit(monkeypatch):
    monkeypatch.setenv('MODEL_API_KEY','secret')
    monkeypatch.setattr(httpx.Client,'post',lambda self,url,**kw:httpx.Response(200,json={'choices':[]},request=httpx.Request('POST',url)))
    with pytest.raises(agent.ModelFailure) as failure:agent.completion([])
    assert failure.value.category=='response_format'
    assert failure.value.metadata['parse_status']=='invalid_envelope'


def test_report_check_links_are_bound_to_own_run(client,session):
    report=report_for(session)
    result=agent.report_links('[检查](#mapping) [未知](#unknown) [执行](#'+report['run_id']+')',report)
    assert '](/' not in result
    assert '(#'+report['run_id']+'-mapping)' in result
    assert '(#unknown)' in result
    case=json.loads((s.package(session)/'public_cases.json').read_text())[1]
    domain=evidence.public_coverage('rag',case)['valid_input_domain']
    assert '非连续子集与空集' in domain and '不属于验收契约' in domain
