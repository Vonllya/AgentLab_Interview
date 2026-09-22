import json
import pytest
from backend import generation_format as fmt, generation as g, generation_flow as flow, generation_roles as roles, agent
from backend.generation_direct import Bundle
from backend.generation_schema import Request, Project
from backend.generation_handoff import NeedsReview


def test_error_categories():
    with pytest.raises(json.JSONDecodeError) as e:json.loads('{"project":')
    assert fmt.classify(e.value)['category']=='json_syntax'
    # Sanitized reproductions of historic double-encoding and prose-in-object failures.
    for value in ['{"app.py":"code"}','app.py: code']:
        with pytest.raises(ValueError) as e:Project.model_validate(dict(normal=value,faulty={},reference={},evasions={'a':{},'b':{}},fault_explanation='enough explanation',evasion_explanations={}))
        feedback=fmt.classify(e.value)
        assert feedback['category']=='schema_shape' and feedback['details'][0]['path']=='normal'
        assert 'dict_type'==feedback['details'][0]['type']


def test_request_mode(monkeypatch):
    monkeypatch.setenv('MODEL_BASE_URL','https://api.deepseek.com/v1')
    monkeypatch.delenv('GENERATION_JSON_MODE',raising=False)
    assert agent.request_options('generation')['response_format']=={'type':'json_object'}
    assert 'response_format' not in agent.request_options('report')
    monkeypatch.setenv('MODEL_BASE_URL','https://unknown.invalid')
    assert 'response_format' not in agent.request_options('generation')
    monkeypatch.setenv('GENERATION_JSON_MODE','json_object')
    assert 'response_format' in agent.request_options('generation')


def test_same_response_correction_budget_and_isolation(client,monkeypatch):
    job=g.create(Request(requirement='格式协议测试，仅本地夹具'),direct_build=True,handoff=True)
    job['mode']='real';g.put(job)
    captured=[]
    def bad(messages,**kwargs):
        captured.append(messages)
        return {'content':'{"project":','_meta':{'usage':{'completion_tokens':10}}}
    monkeypatch.setattr(agent,'completion',bad)
    for _ in range(2):
        with pytest.raises(json.JSONDecodeError):flow.call(job,'project_build')
    with pytest.raises(NeedsReview):flow.call(job,'project_build')
    assert job['budget']['requests']==3 and len(captured)==3
    assert 'original_response' in captured[1][1]['content']
    assert fmt.messages(job,'evaluation',[{'role':'user','content':'public contract only'}])==[{'role':'user','content':'public contract only'}]
    assert job['attempts'][-1]['failure_kind']=='json_syntax'
    assert not job['assets']


def test_format_success_retains_all_validation(client,monkeypatch):
    from backend.generation_mock import role_response
    job=g.create(Request(requirement='格式协议测试，仅本地夹具'),direct_build=True,handoff=True)
    valid=role_response('project_build',roles.context(job,'project_build'))
    job['mode']='real';g.put(job)
    calls=[]
    def reply(messages,**kwargs):
        calls.append(messages)
        text='{"project":' if len(calls)==1 else json.dumps(valid)
        return {'content':text,'_meta':{'usage':{'completion_tokens':10}}}
    monkeypatch.setattr(agent,'completion',reply)
    with pytest.raises(json.JSONDecodeError):flow.call(job,'project_build')
    result=flow.call(job,'project_build')
    assert result==Bundle.model_validate(valid).model_dump()
    assert not job.get('format_correction') and job['budget']['requests']==2


def test_business_validation_is_not_format_repair(client):
    from backend.generation_mock import role_response
    job=g.create(Request(requirement='格式约束分流测试'),direct_build=True,handoff=True)
    data=role_response('project_build',roles.context(job,'project_build'))
    data['project']['faulty']=data['project']['normal']
    with pytest.raises(ValueError) as e:Bundle.model_validate(data)
    assert fmt.classify(e.value)['category']=='asset_constraint'
    fmt.rejected(job,'project_build',e.value,'unused')
    assert not job.get('format_correction')
