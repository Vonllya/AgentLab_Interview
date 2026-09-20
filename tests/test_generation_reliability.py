"""Rollback of optimizations 1–5; preserve presentation, old evidence and original boundaries."""
import copy
import json
import pytest
from backend import generation as g, generation_flow as f, generation_roles as roles, generation_budget as b, generation_mock as mock
from backend import generation_reliability as presentation, contract_revision as c
from test_generation_flow import prepared,matrix,wait,TERMINAL
from test_contract_revision import job_with_mistranscription,correction,checked


def test_removed_model_requirements_and_execution_policies(client):
    job=prepared();job['matrix']=matrix(job)
    assert not {'missing_evidence','evidence_sufficient','evidence_reason'} & set(roles.RepairPlan.model_fields)
    assert 'impact_checks' not in c.Check.model_fields
    assert not hasattr(presentation,'no_progress') and not hasattr(presentation,'before_validation')
    assert 'reliability_version' not in job
    for stage in ('diagnosis','evaluation','contract_check'):
        if stage=='contract_check':checked(job,{'contract_hash':job['contract_hash'],'decision':'clear','reason':'此处为协议验证夹具，不修改任何契约内容。','changes':[],'questions':[]})
        messages=json.dumps(roles.messages(job,stage),ensure_ascii=False)
        assert 'evidence_sufficient' not in messages and 'impact_checks' not in messages
        assert 'counterexample_review' not in messages and 'current_check_ids' not in messages


def test_repeated_invalid_diagnosis_uses_original_budget_not_stagnation(client,monkeypatch):
    job=prepared();job.update(matrix=matrix(job),budget=b.initialize(b.BudgetPolicy(requests=5)),diagnostic_strategy='counterexample_review',stagnation_count=10,diagnosis_rejections={'old':10});g.put(job)
    original=mock.role_response
    def bad(stage,payload):
        response=original(stage,payload)
        if stage=='diagnosis':response['failure_ids']=['invalid-evidence']
        return response
    monkeypatch.setattr(mock,'role_response',bad)
    g.launch(job['id'],'diagnosis');done=wait(job['id'])
    assert done['status']=='budget_exhausted' and done['budget']['requests']==5
    assert len(done['failure_history'])==5


def test_legacy_stopped_job_explicit_resume_preserves_budget(client,monkeypatch):
    job=prepared();job.update(status='no_progress',checkpoint='repair_build',matrix=matrix(job),reliability_version='reliability-v1',format_error={'stage':'diagnosis','reason':'证据不足只能先补契约内覆盖'},failure_history=[{'error':'旧错误保留'}]);g.put(job)
    before=g.get(job['id']);calls=[]
    monkeypatch.setattr(g,'launch',lambda id,stage:calls.append((id,stage)) or g.public(g.get(id)))
    f.resume(job['id'])
    assert calls==[(job['id'],'diagnosis')] and g.get(job['id'])['budget']==before['budget']
    assert g.get(job['id'])['matrix']==before['matrix']
    assert 'format_error' not in g.get(job['id']) and g.get(job['id'])['failure_history']==before['failure_history']


def test_local_contract_check_no_longer_requires_six_dimensions(client):
    job=job_with_mistranscription();checked(job,correction(job))
    assert 'impact_checks' not in job['contract_decision']['result']
    before=copy.deepcopy(job['contract']);assert c.apply(job)=='build'
    assert job['contract_version']==2 and job['contract_history'][-1]['contract']==before


def test_historical_completed_check_extension_remains_readable(client):
    job=job_with_mistranscription();checked(job,correction(job))
    legacy=[{'path':'/behaviors/sum','meaning':'旧记录只读扩展'}]
    job['contract_decision']['result']['impact_checks']=copy.deepcopy(legacy)
    assert c.apply(job)=='build'
    assert job['contract_reviews'][-1]['review']['impact_checks']==legacy


def test_retained_author_summary_and_private_boundary(client):
    job=prepared();job['matrix']=matrix(job);job['matrix']['evasion_witnesses']=[{'input':'PRIVATE_LEGACY_DATA'}];g.put(job)
    before=copy.deepcopy(g.get(job['id']))
    author=g.review_assets(job['id']);public=g.public(job)
    assert author['summary']['variant_results'] and author['summary']['binding']['instance']==job['id']
    assert 'summary' not in public and 'PRIVATE_LEGACY_DATA' not in json.dumps(public)
    assert g.get(job['id'])==before


def test_usage_unknown_still_not_invented(client):
    job=prepared();job['attempts']=[{'metadata':{'usage':{'prompt_tokens':12,'completion_tokens':3}}},{'metadata':{}}]
    usage=presentation.usage(job)['fields']
    assert usage['total_tokens']=={'reported':0,'missing':2}
    assert usage['completion_tokens']=={'reported':3,'missing':1}


def test_generated_docker_rollback_runs_fresh_without_extra_gates(client):
    if not g.executor.availability()[0]:pytest.skip('Docker unavailable; no host fallback')
    job=prepared();job['reliability_version']='reliability-v1';g.validate(job)
    old=copy.deepcopy(job['matrix']);job.update(status='interrupted',diagnostic_strategy='counterexample_review',stagnation_count=10)
    job['progress_history']=[{'asset_hash':g.digest({'contract':job['contract_hash'],'assets':{k:g.digest(g.asset(job,k)) for k in ('build','evaluation')}}),'matrix_id':old['id']}]
    g.put(job);g.launch(job['id'],'validation');done=wait(job['id'])
    assert done['status']=='awaiting_review',done.get('error')
    assert done['matrix']['id']!=old['id'] and done['matrix']['passed']
    assert set(done['matrix']['gates'])=={'normal','reference','fault_trigger','fault_regression','evasion_rejected','no_runtime_errors'}
    assert 'evasion_witnesses' not in done['matrix']
    assert not (g.s.DATA/'generation-regressions').exists()
    assert done['progress_history']==job['progress_history']
    assert done['validation_history'][-1]==old
