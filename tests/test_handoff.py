import copy
import json
import pytest
from pydantic import ValidationError
from backend import generation as g, generation_flow as f, generation_roles as roles
from backend import generation_handoff as h, generation_mock as mock, generation_budget as budget
from test_generation_direct import built


def prepared():
    j=built();f.call(j,'evaluation');f.call(j,'fingerprint');j['handoff_version']=h.VERSION
    project=g.asset(j,'build');evaluation=g.asset(j,'evaluation')
    rows=[]
    for variant in ['normal','reference','faulty',*project['evasions']]:
        for c in evaluation['cases']:
            rows.append({'id':variant+'-'+c['id'],'case':c['id'],'version':variant,'visibility':c['visibility'],
                         'group':c['group'],'covers':c['covers'],'status':'failed' if variant=='faulty' else 'passed',
                         'actual':'HIDDEN_ACTUAL' if c['visibility']=='hidden' else c['expected'],'expected':c['expected']})
    j['matrix']={'id':'matrix','build_hash':g.digest(project),'evaluation_hash':g.digest(evaluation),'fingerprint_hash':g.digest(g.asset(j,'fingerprint')),
        'gates':{'normal':True,'reference':True,'fault_trigger':True,'fault_regression':False,'evasion_rejected':False,'no_runtime_errors':True},'checks':rows,'passed':False}
    g.put(j);return j


def order(j):
    behavior=next(iter(j['contract']['behaviors']))
    return {'action':{'kind':'edit_code','variants':['faulty'],'edits':[{'variant':'faulty','path':'app.py','location':'scenario入口','current_behavior':'当前回归分支未满足公开行为要求。','intended_behavior':'修改未受故障影响分支，使回归行为符合契约。','must_preserve':'指定故障在原触发条件下继续出现，其他版本保持不变。'}]},
            'evidence':[{'check_ids':[next(c['id'] for c in j['matrix']['checks'] if c['version']=='faulty')],
                         'behavior_id':behavior,'quote':j['contract']['behaviors'][behavior]}],'resolutions':[]}


def test_mutually_exclusive_actions_and_evidence(client):
    j=prepared();raw=order(j)
    bad=copy.deepcopy(raw);bad['action']['evaluation_action']='classification'
    with pytest.raises(ValidationError):h.validate_order(j,bad)
    bad=copy.deepcopy(raw);bad['evidence'][0]['quote']='不存在的公开原文'
    with pytest.raises(ValueError,match='公开行为'):h.validate_order(j,bad)
    bad=copy.deepcopy(raw);bad['action']['variants']=['normal'];bad['action']['edits'][0]['variant']='normal'
    with pytest.raises(ValueError,match='禁止修改'):h.validate_order(j,bad)
    bad=copy.deepcopy(raw);bad['action']['edits'][0]['path']='../private.py'
    with pytest.raises(ValueError,match='契约允许'):h.validate_order(j,bad)
    p=h.validate_order(j,raw);assert p['category']=='implementation' and p['target_variants']==['faulty']
    j['pending_plan']=p;ctx=roles.context(j,'repair_build')
    assert 'HIDDEN_ACTUAL' not in json.dumps(ctx)
    assert any(v.get('observation') for v in ctx['obligations'].values())
    assert 'obligations' not in roles.context(j,'evaluation')


def test_builder_conflict_roundtrip_and_bounded_stop(client):
    j=prepared();j['pending_plan']=h.validate_order(j,order(j))
    refs=list(h.obligations(j,['faulty']))
    reply={'result':{'kind':'constraint_conflict','pairs':[{'left_ref':refs[0],'right_ref':'frozen_fault','explanation':'当前要求既保留同一故障又消除相同路径上的故障，需核对检查分类。'}]}}
    assert h.builder_result(j,reply) is None
    assert 'open_conflict' in roles.context(j,'diagnosis')
    raw=order(j)
    with pytest.raises(ValueError,match='回应当前冲突'):h.validate_order(j,raw)
    raw['resolutions']=[{'conflict_id':j['open_conflict']['id'],'disposition':'different_conditions','explanation':'将正常输入和故障触发条件分别处理，仍需执行验证确认条件确实不同。'}]
    assert h.validate_order(j,raw)['category']=='implementation'
    reply['result']['pairs'][0]['explanation']='重新措辞不能算新证据，相同义务冲突仍然没有得到真正解决。'
    with pytest.raises(h.NeedsReview):h.builder_result(j,reply)
    assert len(j['handoff_conflicts'])==2


def test_classification_uses_independent_reviewer_and_preserves_expected(client):
    j=prepared();raw=order(j);case=g.asset(j,'evaluation')['cases'][0]
    raw['evidence'][0]['check_ids']=['faulty-'+case['id']]
    raw['action']={'kind':'reclassify','changes':[{'case_id':case['id'],'before':case['group'],'after':'target' if case['group']=='regression' else 'regression',
        'design_quote':j['private_fault_requirements'],'rationale':'按冻结故障触发条件核对分类，不改变任何输入或正确期望。'}]}
    plan=h.validate_order(j,raw)
    assert plan['category']=='evaluation' and plan['target_variants']==[] and plan['evaluation_action']=='classification'
    j['evaluation_repair']=plan
    ctx=roles.context(j,'evaluation')
    assert 'independent_review' in ctx and 'proposed_action' in ctx
    assert 'project' not in ctx and 'HIDDEN_ACTUAL' not in json.dumps(ctx)
    assert ctx['allowed_field']=='group'


def test_candidate_quarantine_and_acceptance(client,tmp_path):
    j=prepared();old=j['assets']['build'];candidate=g.asset(j,'build');candidate['faulty']['app.py']+='\n# candidate\n'
    directory=g.root(j)/'candidate';directory.mkdir()
    f.save_candidate(j,'build',candidate,directory)
    assert j['assets']['build']==old and g.asset(j,'build')==candidate
    with pytest.raises(ValueError,match='实际门禁'):h.accept_candidates(j)
    h.record_validation(j)
    assert j['candidate_history'][-1]['status']=='rejected'
    with pytest.raises(h.NeedsReview):h.record_validation(j)
    j['matrix']['passed']=True
    with pytest.raises(ValueError,match='资产摘要'):h.accept_candidates(j)
    j['matrix'].update(contract_hash=j['contract_hash'],build_hash=g.digest(candidate))
    h.accept_candidates(j)
    assert j['assets']['build']=='candidate' and not j.get('candidate_assets')
    assert (g.root(j)/old/'output.json').exists()


def test_full_coordinator_conflict_stops_without_budget_drain(client,monkeypatch):
    j=prepared();j['budget']=budget.initialize();j['attempts']=[];j['request_count']=0;g.put(j)
    base=order(j)
    def response(stage,ctx):
        if stage=='diagnosis':
            raw=copy.deepcopy(base)
            if ctx.get('open_conflict'):
                raw['resolutions']=[{'conflict_id':ctx['open_conflict']['id'],'disposition':'different_conditions','explanation':'提供不同条件的假设以进行受控尝试，不代表已证明正确或冲突解决。'}]
            return raw
        if stage=='repair_build':
            return {'result':{'kind':'constraint_conflict','pairs':[{'left_ref':'requirement:faulty:all_regression_checks_pass','right_ref':'frozen_fault',
                'explanation':'必须保留的冻结故障与当前回归义务冲突，需要核对故障范围和检查分类。'}]}}
        raise AssertionError(stage)
    monkeypatch.setattr(mock,'role_response',response)
    assert g.POOL.acquire(blocking=False);g.ACTIVE.add(j['id'])
    f.run(j['id'],'diagnosis');done=g.get(j['id'])
    assert done['status']=='needs_manual_review' and done['request_count']==4
    assert done['assets']==j['assets'] and not done.get('candidate_assets')
    assert len(done['handoff_conflicts'])==2
    assert done['budget']['requests']<done['budget']['policy']['requests']
    assert g.public(done)['status']=='needs_manual_review'
    assert 'handoff_conflicts' not in g.public(done)


def test_insufficient_evidence_requires_named_obligation(client):
    j=prepared();j['pending_plan']=h.validate_order(j,order(j))
    reply={'result':{'kind':'insufficient_evidence','requirement_refs':['nonexistent'],
        'missing':'没有看到具体反例，无法说明条件差异是否成立。','proposed_verification':'请求独立评测根据公开规范核对回归分类与故障范围。'}}
    with pytest.raises(ValueError,match='真实工单义务'):h.builder_result(j,reply)
    reply['result']['requirement_refs']=['requirement:faulty:all_regression_checks_pass']
    assert h.builder_result(j,reply) is None
    raw=order(j);raw['action']={'kind':'need_evidence','missing':reply['result']['missing'],'proposed_verification':reply['result']['proposed_verification'],'requests':[{'kind':'file','variant':'faulty','path':'app.py','question':'确认故障入口调用'}]}
    raw['resolutions']=[{'conflict_id':j['open_conflict']['id'],'disposition':'insufficient_evidence','explanation':'需要核对完整回归与故障范围的关系，再决定代码修复还是分类修复。'}]
    assert h.validate_order(j,raw)['work_order']['action']['kind']=='need_evidence'


def test_real_docker_candidate_must_pass_before_acceptance(client):
    ok,reason=g.executor.availability()
    if not ok:pytest.skip(reason)
    j=built();f.call(j,'evaluation');f.call(j,'fingerprint');j['handoff_version']=h.VERSION
    original=g.asset(j,'build');broken=copy.deepcopy(original);broken['faulty']=copy.deepcopy(original['normal']);broken['faulty']['app.py']+='\n# behavior-equivalent candidate\n'
    base_ref=j['assets']['build'];(g.root(j)/base_ref/'output.json').write_text(json.dumps(broken))
    g.put(j)
    with pytest.raises(ValueError,match='验证门禁失败'):g.validate(j)
    assert j['matrix']['gates']['normal'] and not j['matrix']['gates']['fault_trigger']
    folder=g.root(j)/'repair-candidate';folder.mkdir()
    f.save_candidate(j,'build',original,folder)
    assert j['assets']['build']==base_ref
    matrix=g.validate(j)
    assert matrix['passed'] and j['assets']['build']=='repair-candidate'
    assert j['candidate_history'][-1]['status']=='accepted'
    assert j['candidate_history'][-1]['matrix_id']==matrix['id']
    assert json.loads((g.root(j)/base_ref/'output.json').read_text())==broken
    assert matrix['build_hash']==g.digest(original)


def test_manual_resume_and_interrupted_return_route_back_to_diagnosis(client,monkeypatch):
    j=prepared();j.update(status='needs_manual_review',checkpoint='repair_build');g.put(j)
    launched=[];monkeypatch.setattr(g,'launch',lambda id,stage:launched.append(stage))
    with pytest.raises(ValueError,match='新的依据'):f.resume(j['id'])
    f.resume(j['id'],'已核对公开规则与冻结故障，需要独立复核分类。')
    assert launched==['diagnosis']
    directory=g.root(j)/'conflict-return';directory.mkdir();(directory/'output.json').write_text('{}')
    j.update(status='interrupted',checkpoint='repair_build',attempts=[{'stage':'repair_build','status':'completed','asset':directory.name,'outcome':'returned_to_diagnosis'}]);g.put(j)
    f.resume(j['id']);assert launched==['diagnosis','diagnosis']


def test_pending_candidates_cannot_publish_even_with_stale_passed_matrix(client):
    j=prepared();j.update(status='awaiting_review',candidate_assets={'build':'not-accepted'});j['matrix']['passed']=True;g.put(j)
    with pytest.raises(ValueError,match='候选资产'):g.publish(j['id'],True,'充分长度的测试审核说明','unused')
