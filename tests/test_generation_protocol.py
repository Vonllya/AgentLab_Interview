"""Versioned independent oracles, frozen fault predicates and scoped repair regression."""
import copy
import json
import time
import pytest
from backend import generation as g, generation_flow as f, generation_roles as roles
from backend import generation_mock as mock, generation_protocol as p, generation_diagnostics as d
from backend.generation_schema import Request
from test_generation_flow import wait


def prepared():
    job=g.create(Request(requirement='MOCK 新协议隔离与有界修复回归'))
    design=mock.response('design',{})
    job.update(contract=design['contract'],contract_version=1,confirmed_version=1,contract_hash=g.digest(design['contract']),private_fault_requirements=design['private_fault_requirements'],assessment='simulation',status='interrupted')
    g.put(job)
    for stage in ('build','evaluation','fingerprint'):f.call(job,stage)
    job['status']='interrupted';g.put(job)
    return job


def repair(job,action,targets):
    job['evaluation_repair']={'evaluation_action':action,'target_cases':targets,'contract_behavior_ids':['sum'],'must_preserve_hashes':{'build':g.digest(g.asset(job,'build')),'evaluation':g.digest(g.asset(job,'evaluation'))},'contract_hash':job['contract_hash']}
    return {'evaluation_hash':g.digest(g.asset(job,'evaluation')),'action':action,'changes':[],'additions':[]}


def test_new_protocol_separates_oracle_and_frozen_fault_context(client):
    job=prepared()
    ev=g.asset(job,'evaluation');assert all(c['faulty_expected'] is None for c in ev['cases'])
    assert 'private_fault_requirements' not in roles.context(job,'evaluation')
    context=roles.context(job,'fingerprint')
    assert context['private_fault_requirements']==job['private_fault_requirements']
    assert not any(k in context for k in ('project','matrix','failures','actual'))
    assert 'def total' not in json.dumps(context)
    faults=g.asset(job,'fingerprint');assert p.matches(3,faults['checks'][0])
    assert not p.matches(2,faults['checks'][0])
    wrong=copy.deepcopy(faults);wrong['checks'][0]['assertions'][0]['equals']=2
    with pytest.raises(ValueError,match='正确期望'):p.validate_faults(job,wrong)
    wrong=copy.deepcopy(faults);wrong['checks'][0]['design_quote']='不在冻结设计中的臆测'
    with pytest.raises(ValueError,match='冻结'):p.validate_faults(job,wrong)
    wrong=copy.deepcopy(faults);wrong['checks'][0]['case_id']='normal'
    with pytest.raises(ValueError,match='目标'):p.validate_faults(job,wrong)
    check={'assertions':[{'path':['items','0','ok'],'equals':True}]}
    assert p.matches({'items':[{'ok':True}]},check)
    assert not p.matches({'items':[{'ok':1}]},check)
    assert not p.matches({'items':[]},check)


def test_scoped_patches_cannot_change_oracle_or_add_unapproved_cases(client):
    job=prepared();old=g.asset(job,'evaluation');patch=repair(job,'classification',['negative'])
    patch['changes']=[{'case_id':'negative','field':'group','before':'target','after':'regression','reason':'测试范围授权，不作为真实分类语义成立的证据。'}]
    # Change a different target instead, preserving public/hidden target requirement below.
    patch['changes'][0].update(case_id='normal',before='regression',after='target')
    job['evaluation_repair']['target_cases']=['normal']
    merged=p.merge_patch(job,patch);parsed=d.validate_evaluation_revision(job,merged)
    assert parsed['cases'][0]['expected']==old['cases'][0]['expected']
    assert parsed['cases'][0]['group']=='target'
    bad=copy.deepcopy(patch);bad['changes'][0]['field']='expected'
    with pytest.raises(ValueError,match='越权'):p.merge_patch(job,bad)
    bad=copy.deepcopy(patch);bad['additions']=[old['cases'][0]]
    with pytest.raises(ValueError,match='不能追加'):p.merge_patch(job,bad)
    bad=copy.deepcopy(patch);bad['evaluation_hash']='0'*64
    with pytest.raises(ValueError,match='过期'):p.merge_patch(job,bad)
    bad=copy.deepcopy(patch);bad['changes'][0]['before']='target'
    with pytest.raises(ValueError,match='旧值'):p.merge_patch(job,bad)
    patch=repair(job,'add_coverage',[])
    extra=copy.deepcopy(old['cases'][0]);extra['id']='additional';patch['additions']=[extra]
    assert d.validate_evaluation_revision(job,p.merge_patch(job,patch))['cases'][:-1]==old['cases']
    assert g.asset(job,'evaluation')==old


def test_correct_answer_repair_requires_contract_authorization(client):
    job=prepared();patch=repair(job,'expectation',['normal']);old=g.asset(job,'evaluation')
    patch['changes']=[{'case_id':'normal','field':'expected','before':2,'after':3,'reason':'只有结构有效不代表答案正确，必须经过独立契约授权。'}]
    with pytest.raises(ValueError,match='未经授权'):d.validate_evaluation_revision(job,p.merge_patch(job,patch))
    assert g.asset(job,'evaluation')==old


def test_diagnosis_rejects_fingerprint_disguised_as_oracle(client):
    job=prepared();job['matrix']={'id':'matrix','gates':{'normal':True,'reference':True},'checks':[{'id':'check'}]}
    raw={'category':'evaluation','failure_ids':['check'],'contract_behavior_ids':['sum'],'target_variants':[], 'observed_facts':'正常和参考通过，故障指纹尚未匹配。','hypothesis':'指纹不同','change_request':'修改 faulty_expected 以表达冻结的故障机制。','evaluation_action':'expectation','target_cases':['negative']}
    with pytest.raises(ValueError,match='动作不一致'):d.validate_plan(job,raw)
    raw['evaluation_action']='fingerprint';assert d.validate_plan(job,raw)['evaluation_action']=='fingerprint'


def test_clear_contract_routes_expected_patch_without_rechecking(client,monkeypatch):
    job=prepared();job['matrix']={'id':'matrix','checks':[{'id':'check'}]};job['contract_clarity']={'contract_hash':job['contract_hash']};g.put(job)
    calls=[];original=mock.role_response
    def responses(stage,payload):
        calls.append(stage)
        if stage=='diagnosis':return {'category':'evaluation','failure_ids':['check'],'contract_behavior_ids':['sum'],'target_variants':[], 'observed_facts':'用于路由的确定性测试，不是实际行为证据。','hypothesis':'正常期望需要独立复核','change_request':'只核对指定正确答案的契约依据。','evaluation_action':'expectation','target_cases':['normal']}
        if stage=='evaluation':
            old=payload['previous_evaluation']['cases'][0]['expected']
            return {'evaluation_hash':payload['evaluation_hash'],'action':'expectation','changes':[{'case_id':'normal','field':'expected','before':old,'after':old+1,'reason':'模拟有依据的期望补丁，仅测试路由，不发布。'}],'additions':[]}
        return original(stage,payload)
    monkeypatch.setattr(mock,'role_response',responses)
    monkeypatch.setattr(g.executor,'availability',lambda:(False,'fixture stop before execution'))
    g.launch(job['id'],'diagnosis');done=wait(job['id'])
    assert done['status']=='waiting_environment'
    assert calls==['diagnosis','evaluation','fingerprint']
    assert 'contract_review' not in calls and 'contract_check' not in calls
    assert done['evaluation_review_guided']


def test_generated_docker_v2_classification_repair_and_binding(client,monkeypatch):
    if not g.executor.availability()[0]:pytest.skip('Docker unavailable; no host execution')
    original=mock.role_response
    def responses(stage,payload):
        if stage=='diagnosis':
            checks=payload['matrix']['checks'];c=next(c for c in checks if c['version']=='faulty' and c['case']=='negative-regression')
            return {'category':'evaluation','failure_ids':[c['id']],'contract_behavior_ids':['sum'],'target_variants':[],'observed_facts':'负数输入会触发过滤故障，却被标记为不受影响回归。','hypothesis':'分类错误','change_request':'只把触发负数过滤的输入改为target，保留原正确答案。','evaluation_action':'classification','target_cases':['negative-regression']}
        result=original(stage,payload)
        if stage=='evaluation' and not payload.get('repair_action'):
            result['cases'].append({'id':'negative-regression','group':'regression','visibility':'hidden','covers':['sum'],'input':{'values':[-2,4]},'expected':2,'faulty_expected':None,'classification_reason':'故意构造错误分类以验证实际Docker后的受限修复。'})
        return result
    monkeypatch.setattr(mock,'role_response',responses)
    job=g.create(Request(requirement='MOCK 新协议错误分类实际执行自动修复'))
    g.analyze(job['id']);wait(job['id'],{'awaiting_contract'})
    g.confirm(job['id'],1,True);done=wait(job['id'])
    assert done['status']=='awaiting_review',done.get('error')
    assert done['budget']['validations']==2
    before=done['validation_history'][0];after=done['matrix']
    assert not before['gates']['fault_regression'] and after['passed']
    assert before['build_hash']==after['build_hash']
    assert before['evaluation_hash']!=after['evaluation_hash']
    assert after['fingerprint_hash']==g.digest(g.asset(done,'fingerprint'))
    assert 'fault_checks' not in g.public(done)['matrix']
    assert after['gates']['fingerprint_discriminates']
    initial=json.loads((g.root(done)/next(x['asset'] for x in done['asset_revisions'] if x['stage']=='evaluation')/'output.json').read_text())
    assert [c['expected'] for c in initial['cases']]==[c['expected'] for c in g.asset(done,'evaluation')['cases']]
    frozen=done['review_digest'];fault=g.asset(done,'fingerprint')
    path=g.root(done)/done['assets']['fingerprint']/'output.json'
    fault['checks'][0]['reason']+=' 变更';path.write_text(json.dumps(fault))
    with pytest.raises(ValueError,match='资产已变化'):g.publish(done['id'],True,'MOCK人工审核仅用于平台机制测试',frozen)


def test_completed_fingerprint_checkpoint_resumes_without_model_or_noop(client,monkeypatch):
    job=prepared();before=job['request_count']
    job.update(checkpoint='fingerprint',status='interrupted',evaluation_repair={'evaluation_action':'fingerprint','target_cases':['negative']})
    g.put(job);launched=[]
    monkeypatch.setattr(g,'launch',lambda id,stage:launched.append(stage))
    f.resume(job['id'])
    result=g.get(job['id'])
    assert launched==['validation'] and result['request_count']==before
    assert 'evaluation_repair' not in result


def test_fault_patch_does_not_touch_unselected_or_use_executable_predicates(client):
    job=prepared();faults=g.asset(job,'fingerprint')
    job['evaluation_repair']={'evaluation_action':'fingerprint','target_cases':['multiple']}
    changed=copy.deepcopy(faults);changed['checks'][0]['assertions'][0]['equals']=4
    with pytest.raises(ValueError,match='范围'):p.validate_faults(job,changed)
    changed=copy.deepcopy(faults);changed['checks'][0]['assertions'][0]['python']='import os'
    with pytest.raises(ValueError):p.validate_faults(job,changed)
    with pytest.raises(ValueError,match='无变化'):p.validate_faults(job,faults)


def test_evasion_evidence_identifies_the_actual_unmet_variant(client):
    job=prepared()
    job['matrix']={'id':'matrix','gates':{'evasion_rejected':False},'checks':[
        {'id':'a-target','version':'absolute','group':'target','status':'failed'},
        {'id':'a-regression','version':'absolute','group':'regression','status':'passed'},
        {'id':'f-target','version':'first','group':'target','status':'passed'},
        {'id':'f-regression','version':'first','group':'regression','status':'passed'}]}
    ctx=roles.context(job,'diagnosis')['evasion_results']
    assert ctx['absolute']['satisfies_existing_gate'] is True
    assert ctx['first']['satisfies_existing_gate'] is False
    assert ctx['absolute']['target_failure_ids']==['a-target']
    assert ctx['first']['target_failure_ids']==[]
