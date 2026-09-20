"""Role coordinator regressions. Only docker tests execute candidate programs."""
import copy
import json
import time
import pytest
from backend import generation as g, generation_budget as b, generation_flow as f
from backend import generation_roles as roles, generation_diagnostics as d, generation_mock as mock
from backend.generation_schema import Request
from backend.app import Regenerate

TERMINAL={'awaiting_review','budget_exhausted','waiting_environment','waiting_provider','awaiting_contract_review','awaiting_requirement','failed'}

def wait(id,states=TERMINAL,timeout=150):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        job=g.get(id)
        if job['status'] in states and id not in g.ACTIVE:return job
        time.sleep(.03)
    raise AssertionError(g.public(g.get(id)))

def prepared():
    job=g.create(Request(requirement='明确标记的离线协调器测试'))
    job.pop('generation_protocol',None)  # Legacy persisted-job compatibility fixture.
    design=mock.response('design',{})
    job.update(contract=design['contract'],contract_version=1,confirmed_version=1,contract_hash=g.digest(design['contract']),private_fault_requirements='SECRET FAULT',assessment='simulation',status='interrupted')
    g.put(job)
    f.call(job,'build');f.call(job,'evaluation')
    job['status']='interrupted';g.put(job)
    return job

def matrix(job,passed=False):
    return {'id':'matrix-a','passed':passed,'build_hash':g.digest(g.asset(job,'build')),'evaluation_hash':g.digest(g.asset(job,'evaluation')),'checks':[{'id':'check-a','visibility':'public','status':'failed','case':'negative','version':'faulty','actual':2,'expected':2},{'id':'check-secret','visibility':'hidden','status':'failed','actual':'SECRET OUTPUT','expected':'SECRET EXPECTED'}]}

def plan(job):
    return d.validate_plan(job,mock.role_response('diagnosis',roles.context(job,'diagnosis')))

def test_budget_conservative_and_bounded():
    job={'budget':b.initialize(b.BudgetPolicy(requests=2,output_tokens=6000))}
    cap=b.reserve(job,'design',10);a={'reserved_tokens':cap};b.settle(job,a,{'usage':{'completion_tokens':100}})
    assert job['budget']['output_charged']==100
    cap=b.reserve(job,'diagnosis',20);a={'reserved_tokens':cap};b.settle(job,a,{})
    assert a['usage_unknown'] and job['budget']['output_charged']==3100
    with pytest.raises(b.Exhausted):b.reserve(job,'design',1)
    assert job['budget']['requests']==2
    job['budget']['active_seconds']=1201
    with pytest.raises(b.Exhausted):b.validation(job)


def test_context_and_scoped_asset_guards(client):
    job=prepared();job['matrix']=matrix(job);p=plan(job);p['change_request']='SECRET HIDDEN CASE IN REVIEWER PROSE';job['pending_plan']=p
    public=json.dumps(roles.context(job,'repair_build'))
    assert 'SECRET OUTPUT' not in public and 'SECRET EXPECTED' not in public and 'REVIEWER PROSE' not in public
    assert roles.context(job,'repair_build')['public_observations'][0]['input']=={'values':[-1,3]}
    blind=json.dumps(roles.context(job,'evaluation'))
    assert 'SECRET FAULT' not in blind and 'calculator.py' in blind and 'def total' not in blind
    bad=copy.deepcopy(p);bad['failure_ids']=['other-job-check']
    # Parsed proposals exclude coordinator-added audit fields.
    bad={k:v for k,v in bad.items() if k in roles.RepairPlan.model_fields}
    with pytest.raises(ValueError,match='当前矩阵'):d.validate_plan(job,bad)
    repair={'variants':{'normal':g.asset(job,'build')['normal']},'explanations':{'normal':'不得修改未授权版本'}}
    with pytest.raises(ValueError,match='指定版本'):d.merge_repair(job,repair)
    old=g.asset(job,'evaluation');job['evaluation_repair']={**p,'evaluation_action':'add_coverage','target_cases':[]}
    bad=copy.deepcopy(old);bad['cases'][0]['expected']=99
    with pytest.raises(ValueError,match='未经授权'):d.validate_evaluation_revision(job,bad)
    bad=copy.deepcopy(old);bad['cases']=bad['cases'][1:]
    with pytest.raises(ValueError):d.validate_evaluation_revision(job,bad)


def test_format_failures_continue_until_budget(client,monkeypatch):
    job=g.create(Request(requirement='离线协议失败与预算终止测试'))
    job['budget']=b.initialize(b.BudgetPolicy(requests=4));g.put(job)
    calls=[]
    def invalid(stage,payload):calls.append(stage);return {'invalid':True}
    monkeypatch.setattr(mock,'role_response',invalid)
    g.analyze(job['id']);done=wait(job['id'])
    assert done['status']=='budget_exhausted' and len(calls)==4
    assert len(done['failure_history'])==4 and done['budget']['requests']==4
    time.sleep(.1);assert len(calls)==4


def test_environment_pause_without_model_request(client,monkeypatch):
    job=prepared();before=job['request_count']
    monkeypatch.setattr(g.executor,'availability',lambda:(False,'socket permission denied'))
    g.launch(job['id'],'validation');done=wait(job['id'])
    assert done['status']=='waiting_environment' and done['request_count']==before
    assert done['budget']['validations']==0


def test_new_batch_idempotency_parent_immutable(client,monkeypatch):
    job=prepared();job.update(status='budget_exhausted',matrix=matrix(job));g.put(job)
    frozen=g.get(job['id']);launched=[]
    monkeypatch.setattr(g,'launch',lambda id,stage:launched.append((id,stage)))
    body=Regenerate(expected_revision=job['revision'],idempotency_key='test-key-123',new_batch=True,budget=b.BudgetPolicy(requests=5),repair_note='根据公开契约重新核对错误版本')
    first=f.regenerate(job['id'],body);second=f.regenerate(job['id'],body)
    assert first['id']==second['id'] and len(launched)==1
    assert g.get(job['id'])==frozen and first['parent_job']==job['id']
    assert first['budget']['requests']==0 and first['budget']['policy']['requests']==5
    assert g.asset(g.get(first['id']),'evaluation')==g.asset(job,'evaluation')
    body.repair_note='修改后的不同请求'
    with pytest.raises(ValueError,match='幂等键'):f.regenerate(job['id'],body)


def test_restart_marks_unknown_and_requires_explicit_resume(client):
    job=g.create(Request(requirement='离线重启恢复测试'))
    reserved=b.reserve(job,'build',100)
    job.update(status='building',checkpoint='build',attempts=[{'stage':'build','status':'running','reserved_tokens':reserved}]);g.put(job)
    g.recover();done=g.get(job['id'])
    assert done['status']=='interrupted' and done['attempts'][0]['status']=='outcome_unknown'
    assert done['budget']['output_charged']==12000


def test_generated_docker_automatic_scoped_repair(client,monkeypatch):
    if not g.executor.availability()[0]:pytest.skip('Docker unavailable; never execute on host')
    original=mock.role_response
    def wrong_initial(stage,payload):
        result=original(stage,payload)
        if stage=='build':
            result['faulty']=copy.deepcopy(result['normal'])
            result['faulty']['calculator.py']+='\n# Intentionally equivalent candidate for gate testing\n'
        return result
    monkeypatch.setattr(mock,'role_response',wrong_initial)
    job=g.create(Request(requirement='MOCK 实际 Docker 自动失败修复验证'))
    g.analyze(job['id']);job=wait(job['id'],{'awaiting_contract'})
    g.confirm(job['id'],1,True);done=wait(job['id'])
    assert done['status']=='awaiting_review',done.get('error')
    assert [a['stage'] for a in done['attempts']]==['design','build','evaluation','fingerprint','diagnosis','repair_build','teaching']
    assert done['budget']['validations']==2 and done['repair_round']==1
    old=done['validation_history'][0]
    assert not old['gates']['fault_trigger'] and done['matrix']['passed']
    assert old['evaluation_hash']==done['matrix']['evaluation_hash']
    previous=next(a for a in done['asset_revisions'] if a['stage']=='build')
    prior=json.loads((g.root(done)/previous['asset']/'output.json').read_text())
    current=g.asset(done,'build')
    for key in ('normal','reference','evasions'):assert prior[key]==current[key]
    assert all(c['status']!='error' for c in done['matrix']['checks'])


def test_provider_authentication_pauses_and_unknown_usage(client,monkeypatch):
    from backend import agent
    job=g.create(Request(requirement='离线供应商失败分类回归'));job['mode']='real';g.put(job)
    def denied(*args,**kwargs):raise agent.ModelFailure('authentication','供应商拒绝凭据')
    monkeypatch.setattr(agent,'completion',denied)
    g.analyze(job['id']);done=wait(job['id'])
    assert done['status']=='waiting_provider' and done['request_count']==1
    assert done['budget']['unknown_usage']==1 and done['budget']['output_charged']==4000


def test_cancellation_discards_late_model_result(client,monkeypatch):
    import threading
    from backend import agent
    called=threading.Event();release=threading.Event()
    def delayed(*args,**kwargs):
        called.set();release.wait(3)
        return {'content':json.dumps(mock.response('design',{})),'_meta':{}}
    monkeypatch.setattr(agent,'completion',delayed)
    job=g.create(Request(requirement='离线取消与迟到模型返回测试'));job['mode']='real';g.put(job)
    g.analyze(job['id']);assert called.wait(2)
    g.cancel(job['id']);release.set();done=wait(job['id'],{'cancelled'})
    assert not done['assets'] and done['status']=='cancelled'
    assert done['budget']['requests']==1


def test_evaluation_coverage_repair_preserves_existing_checks(client):
    job=prepared();job['matrix']=matrix(job);p=plan(job)
    job['evaluation_repair']={**p,'category':'evaluation','evaluation_action':'add_coverage','target_cases':[],'target_variants':[]}
    old=g.asset(job,'evaluation');new=copy.deepcopy(old)
    new['cases'].append({'id':'more_negative','group':'target','visibility':'hidden','covers':['sum'],'input':{'values':[-2,1]},'expected':-1,'faulty_expected':1})
    fixed=d.validate_evaluation_revision(job,new)
    assert fixed['cases'][:-1]==old['cases']
    ctx=json.dumps(roles.context(job,'evaluation'))
    assert 'def total' not in ctx and 'SECRET FAULT' not in ctx


def test_expected_fault_failure_is_not_a_broken_generator_variant(client):
    job=prepared();job['matrix']=matrix(job)
    job['matrix']['gates']={'normal':True,'reference':True,'fault_trigger':True,'fault_regression':True,'evasion_rejected':False,'no_runtime_errors':True}
    with pytest.raises(ValueError,match='预期故障'):plan(job)


def test_timeout_retries_with_unknown_usage_until_budget(client,monkeypatch):
    from backend import agent
    job=g.create(Request(requirement='离线超时与用量未知测试'));job['mode']='real';job['budget']=b.initialize(b.BudgetPolicy(requests=2));g.put(job)
    def timeout(*args,**kwargs):raise agent.ModelFailure('timeout','受控超时夹具')
    monkeypatch.setattr(agent,'completion',timeout)
    g.analyze(job['id']);done=wait(job['id'])
    assert done['status']=='budget_exhausted' and done['budget']['requests']==2
    assert done['budget']['unknown_usage']==2
    assert all(a['status']=='outcome_unknown' for a in done['attempts'])


def test_rate_limit_backoff_then_success(client,monkeypatch):
    from backend import agent
    job=g.create(Request(requirement='离线暂时限流后恢复测试'));job['mode']='real';g.put(job)
    attempts=[]
    def response(*args,**kwargs):
        attempts.append(1)
        if len(attempts)==1:raise agent.ModelFailure('rate_limit','受控限流夹具',{'retry_after_seconds':1})
        return {'content':json.dumps(mock.response('design',{})),'_meta':{'usage':{'completion_tokens':100}}}
    monkeypatch.setattr(agent,'completion',response)
    g.analyze(job['id']);done=wait(job['id'],{'awaiting_contract'})
    assert done['budget']['requests']==2 and len(done['failure_history'])==1
    assert done['budget']['output_charged']==4100


def test_completed_checkpoint_resume_does_not_repeat_model(client,monkeypatch):
    job=prepared();job['checkpoint']='evaluation';job['status']='interrupted';g.put(job)
    launches=[];monkeypatch.setattr(g,'launch',lambda id,stage:launches.append(stage))
    f.resume(job['id']);assert launches==['validation']
    assert g.get(job['id'])['request_count']==2


def test_noop_explanation_change_rejected(client):
    job=prepared();job['matrix']=matrix(job);job['pending_plan']=plan(job)
    raw={'variants':{'faulty':g.asset(job,'build')['faulty']},'explanations':{'faulty':'新的说明但代码未改变，应重新诊断'}}
    with pytest.raises(ValueError,match='未改变代码'):d.merge_repair(job,raw)


def test_ambiguous_expectation_waits_for_author(client,monkeypatch):
    job=prepared();job['matrix']=matrix(job);g.put(job)
    original=mock.role_response
    def disputed(stage,payload):
        result=original(stage,payload)
        if stage=='diagnosis':result.update(category='evaluation',target_variants=[],evaluation_action='expectation',target_cases=['negative'],requires_contract_confirmation=True)
        return result
    monkeypatch.setattr(mock,'role_response',disputed)
    before=g.asset(job,'evaluation');g.launch(job['id'],'diagnosis');done=wait(job['id'])
    assert done['status']=='awaiting_requirement' and g.asset(done,'evaluation')==before
    with pytest.raises(ValueError):f.resume(job['id'])


def test_diagnosis_pool_preserves_code_without_duplication(client):
    job=prepared();job['matrix']=matrix(job)
    ctx=roles.context(job,'diagnosis');project=g.asset(job,'build')
    for variant,refs in ctx['project']['variants'].items():
        files={path:ctx['project']['code_pool'][ref] for path,ref in refs.items()}
        assert files==(project[variant] if variant in project else project['evasions'][variant])
    assert len(ctx['project']['code_pool'])<sum(len(f) for f in ctx['project']['variants'].values())


def test_busy_new_batch_is_persisted_and_not_silently_queued(client,monkeypatch):
    job=prepared();job.update(status='budget_exhausted',matrix=matrix(job));g.put(job)
    def busy(*args):raise ValueError('已有生成在执行，请稍后重试')
    monkeypatch.setattr(g,'launch',busy)
    body=Regenerate(expected_revision=job['revision'],idempotency_key='busy-key-123',new_batch=True,budget=b.BudgetPolicy(requests=3))
    result=f.regenerate(job['id'],body)
    assert result['status']=='interrupted' and result['error']['category']=='busy'
    assert result['budget']['requests']==0
    assert f.regenerate(job['id'],body)['id']==result['id']


def test_coordinator_routes_evaluation_only_with_guidance_audit(client,monkeypatch):
    # Deterministic gate fixture, not execution evidence; Docker covered separately.
    job=prepared();old=g.asset(job,'evaluation')
    old['cases'].append({'id':'misclassified','group':'regression','visibility':'public','covers':['sum'],'input':{'values':[-2,1]},'expected':-1,'faulty_expected':None})
    path=g.root(job)/job['assets']['evaluation']/'output.json';path.write_text(json.dumps(old))
    before=g.digest(g.asset(job,'build'));original=mock.role_response
    def responses(stage,payload):
        if stage=='diagnosis':
            result=original(stage,payload)
            result.update(category='evaluation',target_variants=[],evaluation_action='classification',target_cases=['misclassified'])
            return result
        if stage=='evaluation':
            result=copy.deepcopy(payload['previous_evaluation']);result['cases'][-1]['group']='target';return result
        return original(stage,payload)
    def validation(candidate):
        candidate['matrix']=matrix(candidate,passed=g.asset(candidate,'evaluation')['cases'][-1]['group']=='target');g.put(candidate)
        if not candidate['matrix']['passed']:raise ValueError('确定性分类门禁夹具，不计真实执行')
    monkeypatch.setattr(mock,'role_response',responses)
    monkeypatch.setattr(g.executor,'availability',lambda:(True,''));monkeypatch.setattr(g,'validate',validation)
    g.launch(job['id'],'validation');done=wait(job['id'])
    assert done['status']=='awaiting_review' and done['budget']['validations']==2
    assert g.digest(g.asset(done,'build'))==before
    assert done['attempts'][-2]['stage']=='evaluation' and done['attempts'][-2]['blind'] is False
    after=g.asset(done,'evaluation');after['cases'][-1]['group']='regression';assert after==old
