import copy
import json
import time
import pytest
from backend import contract_revision as c, generation as g, generation_flow as f, generation_mock as mock
from backend import generation_roles as roles, generation_budget as b
from backend.generation_schema import Request
from test_generation_flow import prepared,wait,matrix,TERMINAL


def job_with_mistranscription():
    job=prepared()
    job['request']['requirement']='训练整数累加：返回所有整数的算术和，空列表返回0；只使用本地数据。'
    job['contract']['behaviors']['sum']='只累加正数并忽略所有负数'
    job['contract_hash']=g.digest(job['contract']);job['matrix']=matrix(job);job['status']='interrupted';g.put(job)
    return job


def correction(job):
    return {'contract_hash':job['contract_hash'],'decision':'correction','reason':'需求明确要求所有整数，但契约错误排除了负数。','changes':[{'path':'/behaviors/sum','op':'replace','before':job['contract']['behaviors']['sum'],'after':'返回所有整数的算术和','source':'request.requirement','quote':'返回所有整数的算术和','reason':'仅纠正契约对原始需求的错误转述，保留其他要求。'}],'questions':[]}


def checked(job,proposal,verdict='approve'):
    job['contract_candidate']={'proposal':proposal,'hash':g.digest(proposal),'asset':'test-proposal'}
    result=mock.role_response('contract_check',c.context(job,checking=True));result['verdict']=verdict
    job['contract_decision']={'result':result,'asset':'test-review'}


def test_exact_local_change_archives_and_invalidates(client):
    job=job_with_mistranscription();before=copy.deepcopy(job);patch=correction(job);checked(job,patch)
    assert c.apply(job)=='build'
    for key in job['contract']:
        if key!='behaviors':assert job['contract'][key]==before['contract'][key]
    assert job['contract']['behaviors']['empty']==before['contract']['behaviors']['empty']
    assert job['contract_version']==2 and job['confirmed_version']==2
    assert job['assets']=={} and job['matrix'] is None
    assert job['contract_history'][-1]['matrix']==before['matrix']
    assert job['contract_history'][-1]['assets']==before['assets']
    assert job['budget']==before['budget']
    assert job['confirmation']['source']=='grounded_local_correction'
    assert job['checkpoint']=='build'


@pytest.mark.parametrize('mutation',['quote','before','hash','whole','path','default_business','duplicate','no_check'])
def test_invalid_or_ungrounded_patch_rejected(client,mutation):
    job=job_with_mistranscription();p=correction(job)
    if mutation=='quote':p['changes'][0]['quote']='原需求没有这句支持证据'
    if mutation=='before':p['changes'][0]['before']='错误旧值'
    if mutation=='hash':p['contract_hash']='0'*64
    if mutation=='whole':p['changes'][0].update(path='/behaviors',before=job['contract']['behaviors'],after={'sum':'返回0'})
    if mutation=='path':p['changes'][0]['path']='/../files'
    if mutation=='default_business':p['changes'][0].update(source='default.runtime',quote=c.DEFAULTS['runtime'])
    if mutation=='duplicate':p['changes'].append(copy.deepcopy(p['changes'][0]))
    if mutation=='no_check':
        checked(job,p);job['contract_decision']['result']['proposal_hash']='1'*64
        with pytest.raises(ValueError):c.apply(job)
    else:
        with pytest.raises(ValueError):c.validate_proposal(job,p)
    assert job['contract_version']==1


def test_private_diagnostics_never_enter_contract_context(client):
    job=job_with_mistranscription();job.update(private_fault_requirements='SECRET_FAULT',repair_note='SECRET_AUTHOR',contract_origin_plan={'change_request':'SECRET_PROSE'},contract_issue={'behavior_ids':['sum'],'category':'contract','evaluation_action':'none'})
    checked(job,correction(job))
    for stage in ('contract_review','contract_check'):
        ctx=json.dumps(roles.context(job,stage))
        assert 'SECRET_' not in ctx and 'def total' not in ctx and 'faulty_expected' not in ctx
        assert job['request']['requirement'] in json.dumps(roles.context(job,stage),ensure_ascii=False)


def test_disagreement_retries_role_without_mutating_contract(client):
    job=job_with_mistranscription();before=copy.deepcopy(job['contract']);checked(job,correction(job),'revise')
    assert c.apply(job)=='contract_review' and job['contract']==before
    assert job['contract_version']==1 and job['assets'] and job['matrix']
    assert job['checkpoint']=='contract_review'


def test_need_user_answer_revision_idempotency_and_isolation(client,monkeypatch):
    job=job_with_mistranscription();proposal=mock.role_response('contract_review',c.context(job));checked(job,proposal)
    assert c.apply(job) is None and job['status']=='awaiting_requirement'
    question=job['requirement_question'];before=copy.deepcopy(job['contract'])
    launches=[];monkeypatch.setattr(g,'launch',lambda id,stage:launches.append((id,stage)) or g.public(g.get(id)))
    body={'expected_revision':job['revision'],'question_id':question['id'],'answers':{'intent':'所有整数都参与累加，空列表返回0'}}
    wrong={**body,'question_id':'0'*32};assert client.post('/api/generation/jobs/'+job['id']+'/requirement-answer',json=wrong).status_code==400
    result=client.post('/api/generation/jobs/'+job['id']+'/requirement-answer',json=body);assert result.status_code==200
    assert client.post('/api/generation/jobs/'+job['id']+'/requirement-answer',json=body).status_code==200
    assert len(launches)==1 and launches[0][1]=='contract_review'
    saved=g.get(job['id']);assert saved['contract']==before and saved['request']==job['request']
    assert '所有整数都参与累加' in json.dumps(c.sources(saved),ensure_ascii=False)
    assert client.post('/api/generation/jobs/'+job['id']+'/requirement-answer',json={**body,'answers':{'intent':'不同的答案'}}).status_code==400


def test_independent_check_and_review_share_budget(client,monkeypatch):
    job=job_with_mistranscription();job['budget']=b.initialize(b.BudgetPolicy(requests=1));g.put(job)
    original=mock.role_response
    monkeypatch.setattr(mock,'role_response',lambda stage,payload:correction(job) if stage=='contract_review' else original(stage,payload))
    g.launch(job['id'],'contract_review');done=wait(job['id'])
    assert done['status']=='budget_exhausted' and done['contract_version']==1
    assert done['budget']['requests']==1 and done['contract_candidate']
    assert done['checkpoint']=='contract_check'


def test_contract_clear_can_recompute_only_authorized_expectation(client):
    from backend import generation_diagnostics as d
    job=job_with_mistranscription();proposal={'contract_hash':job['contract_hash'],'decision':'clear','reason':'此为独立校核路由夹具，契约不需要修改。','changes':[],'questions':[]}
    plan={'category':'evaluation','evaluation_action':'expectation','target_cases':['normal'],'must_preserve_hashes':{'build':g.digest(g.asset(job,'build'))}}
    job['contract_origin_plan']=plan;checked(job,proposal)
    assert c.apply(job)=='evaluation' and job['contract_version']==1
    old=g.asset(job,'evaluation');updated=copy.deepcopy(old);updated['cases'][0]['expected']=4
    assert d.validate_evaluation_revision(job,updated)==updated
    updated['cases'][1]['expected']=5
    with pytest.raises(ValueError):d.validate_evaluation_revision(job,updated)
    # This validates scope only, not correctness of numeric expectations; real matrix still gates publishing.


def test_generated_docker_contract_local_correction_revalidates(client,monkeypatch):
    if not g.executor.availability()[0]:pytest.skip('Docker unavailable; no host fallback')
    job=job_with_mistranscription();before=copy.deepcopy(job);original=mock.role_response
    def responses(stage,payload):
        if stage=='contract_review':return correction(job)
        return original(stage,payload)
    monkeypatch.setattr(mock,'role_response',responses)
    g.launch(job['id'],'contract_review');done=wait(job['id'],TERMINAL|{'awaiting_requirement'})
    assert done['status']=='awaiting_review',done.get('error')
    assert done['contract_version']==2 and done['matrix']['passed']
    assert done['matrix']['contract_hash']==done['contract_hash']!=before['contract_hash']
    assert done['matrix']['id']!=before['matrix']['id']
    assert done['contract_history'][-1]['matrix']==before['matrix']
    assert [a['stage'] for a in done['attempts'][-5:]]==['contract_review','contract_check','build','evaluation','teaching']
    assert done['budget']['validations']==1


def test_published_and_unconfirmed_contracts_not_auto_changed(client):
    job=job_with_mistranscription();checked(job,correction(job));before=copy.deepcopy(job)
    job['status']='published'
    with pytest.raises(ValueError):c.apply(job)
    assert job['contract']==before['contract'] and 'contract_reviews' not in job
    job['status']='interrupted';job['confirmed_version']=None
    with pytest.raises(ValueError):c.apply(job)
    assert job['contract']==before['contract'] and 'contract_reviews' not in job


def test_completed_contract_check_resumes_without_repaying(client,monkeypatch):
    job=job_with_mistranscription();checked(job,correction(job));job['checkpoint']='contract_check';g.put(job)
    calls=[];monkeypatch.setattr(g,'launch',lambda id,stage:calls.append(stage))
    f.resume(job['id']);assert calls==['contract_apply']
    assert g.get(job['id'])['request_count']==job['request_count']


def test_new_budget_cannot_bypass_pending_user_question(client,monkeypatch):
    from backend.app import Regenerate
    job=job_with_mistranscription();checked(job,mock.role_response('contract_review',c.context(job)));c.apply(job)
    calls=[];monkeypatch.setattr(g,'launch',lambda *args:calls.append(args))
    result=f.regenerate(job['id'],Regenerate(expected_revision=job['revision'],idempotency_key='question-batch-123',new_batch=True,budget=b.BudgetPolicy(requests=4)))
    assert result['status']=='awaiting_requirement' and not calls
    assert result['requirement_question']==job['requirement_question']
