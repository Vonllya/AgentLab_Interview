"""Merged build flow: independence, immutable versions, no confirmation, real Docker."""
import copy
import json
import time
import pytest
from backend import generation as g, generation_flow as f, generation_direct as direct
from backend import generation_roles as roles, generation_mock as mock, generation_budget as b
from backend.generation_schema import Request
from test_generation_flow import wait, TERMINAL


def built():
    j=g.create(Request(requirement='MOCK 合并构建与公开规范平台功能测试'),direct_build=True)
    f.call(j,'project_build');direct.install_bundle(j)
    j['status']='interrupted';g.put(j)
    return j


def test_api_opts_in_and_legacy_creation_stays_compatible(client):
    new=client.post('/api/generation/jobs',json={'requirement':'MOCK 直接构建接口与旧记录兼容验证'}).json()
    assert new['project_flow']==direct.VERSION and new['stage']=='project_build'
    assert not g.create(Request(requirement='MOCK 历史记录兼容测试')).get('project_flow')
    assert client.post('/api/generation/jobs/'+new['id']+'/confirm',json={'version':0,'simulation_confirmed':True}).status_code==400


def test_review_context_excludes_implementation_and_requires_all_output_rules(client):
    j=built();ctx=roles.context(j,'spec_review')
    assert 'project' not in ctx and 'private_fault_requirements' not in ctx
    assert 'def total' not in json.dumps(ctx) and '过滤负数导致累加错误' not in json.dumps(ctx,ensure_ascii=False)
    result=mock.role_response('spec_review',ctx)
    assert direct.validate_review(j,result)['decision']=='approve'
    result['output_rules']=[]
    with pytest.raises(ValueError,match='逐项'):direct.validate_review(j,result)
    result=mock.role_response('spec_review',ctx);result['output_rules'][0]['quote']='只是字段类型不是行为规则'
    with pytest.raises(ValueError,match='判定依据'):direct.validate_review(j,result)
    eval_ctx=roles.context(j,'evaluation')
    assert 'project' not in eval_ctx and 'private_fault_requirements' not in eval_ctx


def test_scope_revisions_archive_and_invalidate_evidence(client):
    j=built();old=copy.deepcopy(j)
    j['spec_review_feedback']={'issues':[{'path':'/simulation','reason':'公开模拟规则缺少了需要明确的边界说明。'}]}
    bundle=g.asset(j,'project_build');bundle['contract']['simulation']+=' 空列表也按公开规则处理。'
    direct.validate_bundle(j,bundle)
    bad=copy.deepcopy(bundle);bad['contract']['title']='未经授权修改标题'
    with pytest.raises(ValueError,match='未授权'):direct.validate_bundle(j,bad)
    folder=g.root(j)/'candidate-revision';folder.mkdir();j['previous_bundle_assets']=copy.deepcopy(j['assets'])
    f.save_candidate(j,'project_build',bundle,folder)
    j.update(matrix={'id':'old-matrix'},review_digest='old-digest',spec_approval={'contract_hash':j['contract_hash']})
    direct.install_bundle(j)
    assert j['contract_version']==2 and j['matrix'] is None and 'review_digest' not in j
    assert j['contract_history'][-1]['matrix']['id']=='old-matrix'
    assert j['contract_history'][-1]['assets']['build']==old['assets']['build']
    assert j['confirmed_version'] is None and 'spec_approval' not in j
    assert (g.root(j)/old['assets']['build']/'output.json').exists()


def test_completed_bundle_resume_does_not_repeat_call(client,monkeypatch):
    j=g.create(Request(requirement='MOCK 构建完成后重启检查点恢复验证'),direct_build=True)
    f.call(j,'project_build');j.update(status='interrupted',checkpoint='project_build');g.put(j)
    calls=[];monkeypatch.setattr(g,'launch',lambda id,stage:calls.append(stage))
    f.resume(j['id']);done=g.get(j['id'])
    assert calls==['spec_review'] and done['request_count']==1 and done['contract_version']==1
    f.resume(j['id']);assert g.get(j['id'])['contract_version']==1


def test_builder_clarification_is_independently_reviewed_and_answered(client,monkeypatch):
    original=mock.role_response
    q={'id':'target','text':'本次训练希望验证哪一种不同的用户目标？','options':['累加计算','过滤计算'],'impact':'目标不同会影响应保留的正常行为。'}
    def responses(stage,payload):
        if stage=='project_build' and not payload.get('requirement_answers'):
            return {'assessment':'clarify','rationale':'MOCK 用户目标确有两种解释的夹具。','questions':[q],'contract':None,'private_fault_requirements':'','project':None}
        return original(stage,payload)
    monkeypatch.setattr(mock,'role_response',responses)
    j=g.create(Request(requirement='MOCK 确需用户目标澄清的隔离测试'),direct_build=True);g.analyze(j['id']);j=wait(j['id'])
    assert j['status']=='awaiting_requirement'
    assert [a['stage'] for a in j['attempts']]==['project_build','spec_review']
    before=j['request_count']
    monkeypatch.setattr(g.executor,'availability',lambda:(False,'fixture stop before execution'))
    payload={'expected_revision':j['revision'],'question_id':j['requirement_question']['id'],'answers':{'target':'累加计算'}}
    res=client.post('/api/generation/jobs/'+j['id']+'/requirement-answer',json=payload);assert res.status_code==200,res.text
    done=wait(j['id']);assert done['status']=='waiting_environment' and done['request_count']>before
    count=done['request_count'];client.post('/api/generation/jobs/'+j['id']+'/requirement-answer',json=payload)
    assert g.get(j['id'])['request_count']==count
    assert done['confirmation']['source']=='independent_specification_review'


def test_evaluator_can_return_specification_issue_without_noop_patch(client,monkeypatch):
    j=built();f.call(j,'spec_review');direct.apply_review(j)
    f.call(j,'evaluation');f.call(j,'fingerprint');j['status']='interrupted'
    evaluation=g.asset(j,'evaluation')
    j['evaluation_repair']={'evaluation_action':'expectation','target_cases':['normal'],'contract_behavior_ids':['sum']}
    original=mock.role_response
    def response(stage,payload):
        if stage=='evaluation':return {'decision':'specification_issue','reason':'MOCK 输出规则缺少可验证的确定性约定，不能盲目改答案。','patch':None,'issues':[{'path':'/simulation','reason':'需要明确公开模拟输出规则而非迎合实现。'}]}
        return original(stage,payload)
    monkeypatch.setattr(mock,'role_response',response);g.put(j)
    result=f.call(j,'evaluation')
    assert result['decision']=='specification_issue' and g.asset(j,'evaluation')==evaluation
    assert j['attempts'][-1]['status']=='completed'
    j.update(status='interrupted',checkpoint='evaluation');g.put(j)
    calls=[];monkeypatch.setattr(g,'launch',lambda id,stage:calls.append(stage))
    f.resume(j['id']);assert calls==['spec_review']


def test_unapproved_spec_cannot_advance_to_tests(client):
    j=built();assert f.next_after_asset(j)=='spec_review'
    with pytest.raises(ValueError):g.publish(j['id'],True,'没有独立审查和执行证据不能发布','0'*64)
    with pytest.raises(ValueError):g.revise(j['id'],direct.Contract.model_validate(j['contract']))


def test_direct_docker_build_review_repair_publish_train(client,monkeypatch):
    if not g.executor.availability()[0]:pytest.skip('Docker unavailable; no host fallback')
    original=mock.role_response;seen=[]
    def response(stage,payload):
        seen.append(stage)
        result=original(stage,payload)
        if stage=='spec_review' and seen.count(stage)==1:
            result.update(decision='revise',reason='MOCK 可验证性审查要求补充公开模拟说明，不是让用户确认。',issues=[{'path':'/simulation','reason':'补充空列表返回0的明确说明以避免推测。'}],output_rules=[])
        if stage=='project_build' and payload.get('review_feedback'):
            result['contract']['simulation']+=' 空列表返回0。'
        return result
    monkeypatch.setattr(mock,'role_response',response)
    j=g.create(Request(requirement='MOCK 直接构建无需契约确认的完整Docker流程'),direct_build=True)
    g.analyze(j['id']);done=wait(j['id'],TERMINAL|{'unsupported'})
    assert done['status']=='awaiting_review',done.get('error')
    assert seen==['project_build','spec_review','project_build','spec_review','evaluation','fingerprint','teaching']
    assert done['contract_version']==2 and done['matrix']['passed']
    assert all(c.get('repeat_count')==2 and c.get('repeat_consistent') for c in done['matrix']['checks'])
    assert done['confirmation']['not_user_approval'] is True
    review=g.review_assets(done['id'])
    publication=g.publish(done['id'],True,'MOCK 自动化审核表单测试，不代表真实用户或真实人工批准。',review['review_digest'])
    from backend import workspace as w
    session=w.create(publication['task_id']);w.save_files(session,g.asset(done,'build')['reference'],'MOCK系统功能验证，不代表学习效果')
    response=client.post('/api/sessions/'+session['id']+'/submit');assert response.status_code==200
    until=time.monotonic()+90
    while time.monotonic()<until:
        state=client.get('/api/sessions/'+session['id']).json()
        if state['reports'] and state['reports'][0]['feedback_status']!='generating':break
        time.sleep(.1)
    assert state['reports'][0]['objective']['status']=='passed'
    behavior=[c for c in state['reports'][0]['objective']['checks'] if c.get('category')=='behavior']
    assert behavior and all(c.get('repeat_count')==2 and c.get('repeat_consistent') for c in behavior)
    assert state['reports'][0]['snapshot']==state['reports'][0]['objective']['snapshot']
    fork=g.fork(done['id']);assert fork['status']=='draft' and fork['project_flow']==direct.VERSION
    assert g.get(done['id'])['status']=='published'


def test_merged_role_budget_fits_model_adapter(client,monkeypatch):
    from backend import agent
    monkeypatch.delenv('MODEL_API_KEY',raising=False)
    for cap in b.ROLE_LIMITS.values():
        with pytest.raises(agent.ModelFailure) as error:
            agent.completion([{'role':'user','content':'budget boundary test'}],purpose='generation',output_limit=cap)
        assert error.value.category=='configuration'  # Adapter accepted cap; no network request.


def test_completed_review_resume_does_not_repeat_call(client,monkeypatch):
    j=built();f.call(j,'spec_review');j.update(status='interrupted',checkpoint='spec_review');g.put(j)
    calls=[];monkeypatch.setattr(g,'launch',lambda id,stage:calls.append(stage))
    f.resume(j['id']);done=g.get(j['id'])
    assert calls==['evaluation'] and done['request_count']==2
    assert done['confirmed_version']==done['contract_version']
    f.resume(j['id']);assert len(g.get(j['id'])['spec_reviews'])==1


def test_review_allows_branch_rules_but_rejects_missing_and_unknown_paths(client):
    j=built();result=mock.role_response('spec_review',roles.context(j,'spec_review'))
    result['output_rules'].append(copy.deepcopy(result['output_rules'][0]))
    assert direct.validate_review(j,result)['decision']=='approve'
    result['output_rules'][0]['path']='/unknown'
    with pytest.raises(ValueError,match='未知路径'):direct.validate_review(j,result)


def test_coverage_feedback_names_gap_and_preserves_blind_review(client,monkeypatch):
    j=built();j['contract']['behaviors']['determinism']='相同输入的输出固定，不含时间戳或随机值。';j['contract_hash']=g.digest(j['contract']);g.put(j)
    with pytest.raises(ValueError,match='determinism'):f.call(j,'evaluation')
    ctx=roles.context(j,'evaluation')
    assert ctx['coverage_feedback']['missing_behaviors']==['determinism']
    assert ctx['previous_rejected_evaluation']['cases']
    j['preflight_review']=True
    review=roles.context(j,'spec_review')
    assert review['preflight_problem']['missing_behaviors']==['determinism']
    assert 'expected' not in json.dumps(review) and 'def total' not in json.dumps(review)
    candidate_path=g.root(j)/j['evaluation_candidate']['asset']/'rejected.json'
    raw=json.loads(candidate_path.read_text());raw['cases'][0]['id']={'private_input':'must_not_leak'}
    candidate_path.write_text(json.dumps(raw))
    assert 'must_not_leak' not in json.dumps(roles.context(j,'spec_review'))


def test_pre_execution_failures_review_then_correct_without_matrix(client,monkeypatch):
    original=mock.role_response;seen=[]
    def respond(stage,payload):
        seen.append(stage);value=original(stage,payload)
        if stage=='evaluation' and seen.count(stage)<=2:
            for c in value['cases']:c['covers']=['sum']
        if stage=='evaluation' and seen.count(stage)==3:
            assert payload['coverage_feedback']['missing_behaviors']==['empty']
            assert payload['previous_rejected_evaluation']['cases']
        return value
    monkeypatch.setattr(mock,'role_response',respond)
    monkeypatch.setattr(g.executor,'availability',lambda:(False,'test checkpoint'))
    j=g.create(Request(requirement='MOCK 首次执行前缺失覆盖的纠错流程'),direct_build=True);g.analyze(j['id'])
    done=wait(j['id'])
    assert done['status']=='waiting_environment'
    assert seen==['project_build','spec_review','evaluation','evaluation','spec_review','evaluation','fingerprint']
    assert done['matrix'] is None and 'evaluation_candidate' not in done
    assert done['contract_version']==1


def test_repeat_execution_detects_inconsistent_normal_even_with_coverage(client,monkeypatch):
    from types import SimpleNamespace
    j=built();f.call(j,'evaluation');f.call(j,'fingerprint');g.put(j)
    monkeypatch.setattr(g.executor,'availability',lambda:(True,''))
    monkeypatch.setattr(g.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout='sha256:test'))
    calls={}
    def execute(folder,data,**kwargs):
        name=folder.name;key=(name,json.dumps(data,sort_keys=True));calls[key]=calls.get(key,0)+1
        values=data['values']
        value=sum(v for v in values if v>=0) if name=='faulty' else sum(abs(v) for v in values) if name=='absolute' else (values[0] if values else 0) if name=='first' else sum(values)
        return value+1 if name=='normal' and calls[key]==2 else value
    monkeypatch.setattr(g.executor,'execute',execute)
    with pytest.raises(ValueError,match='验证门禁失败'):g.validate(j)
    normal=[c for c in j['matrix']['checks'] if c['version']=='normal']
    assert normal and all(c['repeat_count']==2 and not c['repeat_consistent'] and c['status']=='failed' for c in normal)
    assert not j['matrix']['gates']['normal']
    review=roles.context(j,'diagnosis')['matrix']['checks']
    assert any(c.get('repeat_consistent') is False and 'repeat_actual' in c for c in review)
