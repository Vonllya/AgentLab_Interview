import copy
import json
import pytest
from backend import generation as g, generation_flow as flow, generation_roles as roles
from backend import generation_fault_model as fm, generation_protocol as protocol
from backend import generation_handoff as handoff, generation_direct as direct
from backend.generation_schema import Request
from test_handoff import prepared, order


def modeled():
    j=g.create(Request(requirement='验证生成流程的故障影响范围与分类一致性'),direct_build=True,handoff=True,fault_model=True)
    flow.call(j,'project_build');direct.install_bundle(j)
    flow.call(j,'spec_review');direct.apply_review(j)
    flow.call(j,'evaluation');flow.call(j,'fingerprint')
    return j


def test_independent_context_and_freeze(client):
    j=modeled()
    assert 'fault_model' not in json.dumps(roles.context(j,'evaluation'))
    ctx=roles.context(j,'fingerprint')
    assert 'frozen_fault_model' in ctx and len(ctx['impact_cases'])==4
    assert not {'project','matrix','actual','previous_variants'} & set(ctx)
    raw=g.asset(j,'project_build');raw['fault_model']['trigger']['any_of'][0][0]['value']=1
    with pytest.raises(ValueError,match='静默改变'):direct.validate_bundle(j,raw)


def test_classification_uses_trigger_not_test_title_or_actual(client):
    j=modeled();evaluation=g.asset(j,'evaluation');original=copy.deepcopy(evaluation)
    for c in evaluation['cases']:c['group']='regression'
    result=protocol.evaluation(j,evaluation).model_dump()
    assert result==original
    bad=g.asset(j,'fingerprint');bad['impacts'][0]['triggers']=True
    with pytest.raises(ValueError,match='触发规则冲突'):protocol.validate_faults(j,bad)
    bad=g.asset(j,'fingerprint');bad['checks'][0]['assertions'][0]['path']=['invented']
    with pytest.raises(ValueError,match='影响范围'):protocol.validate_faults(j,bad)


def test_predicates_bounded_and_fail_closed():
    model={'trigger':{'any_of':[[{'path':['ready_after'],'quantifier':'value','operator':'gt','value':1}]]}}
    assert fm.triggers(model,{'ready_after':2})
    assert not fm.triggers(model,{'ready_after':1})
    with pytest.raises(ValueError,match='路径不存在'):fm.triggers(model,{})
    with pytest.raises(ValueError,match='数字'):fm.triggers(model,{'ready_after':True})
    with pytest.raises(ValueError):fm.Trigger.model_validate({'any_of':[[]]})
    with pytest.raises(ValueError):fm.Predicate.model_validate({'path':[],'quantifier':'value','operator':'exec','value':'print(1)'})
    assert fm.semantic_equal({'app.py':'x=1\n'},{'app.py':'# comment\nx = 1\n'})
    assert not fm.semantic_equal({'app.py':'x=1\n'},{'app.py':'x=2\n'})


def test_program_agenda_and_noop_candidate(client):
    j=prepared();j['fault_model_version']=fm.VERSION
    # Test fixture uses existing immutable bundle by replacing only isolated test asset.
    p=g.root(j)/j['assets']['project_build']/'output.json';bundle=json.loads(p.read_text())
    bundle['fault_model']={'trigger':{'any_of':[[{'path':['values'],'quantifier':'any','operator':'lt','value':0}]]},'affected_paths':[[]],'preservation':'没有负数的输入仍应得到正确的算术和。'}
    p.write_text(json.dumps(bundle))
    p=g.root(j)/j['assets']['evaluation']/'output.json';ev=json.loads(p.read_text());ev['cases'][2]['input']={'values':[2,-3]};ev['cases'][2]['expected']=-1;p.write_text(json.dumps(ev))
    assert fm.agenda(j)['action']=='edit_code'
    j['pending_plan']=handoff.validate_order(j,order(j))
    files=g.asset(j,'build')['faulty'];files={k:v+'\n# unchanged\n' for k,v in files.items()}
    assert handoff.builder_result(j,{'result':{'kind':'modified','variants':{'faulty':files},'explanations':{'faulty':'只增加注释并不能算作真正的修复。'}}}) is None
    assert j['handoff_conflicts'][-1]['kind']=='unchanged_candidate'
    # Deliberately corrupt only classification, not input/expected.
    p=g.root(j)/j['assets']['evaluation']/'output.json';ev=json.loads(p.read_text());ev['cases'][1]['group']='regression';p.write_text(json.dumps(ev))
    assert fm.agenda(j)['action']=='reclassify'
    with pytest.raises(ValueError,match='程序事项'):fm.validate_action(j,order(j)['action'])


def test_first_ineffective_execution_gets_counterexamples_then_stops(client):
    j=prepared();j['fault_model_version']=fm.VERSION
    handoff.record_validation(j)
    handoff.record_validation(j)
    assert j['candidate_feedback']['matrix_id']==j['matrix']['id']
    with pytest.raises(handoff.NeedsReview):handoff.record_validation(j)


def test_modeled_docker_matrix(client):
    j=modeled()
    ok,reason=g.executor.availability()
    if not ok:pytest.skip(reason)
    matrix=g.validate(j)
    assert matrix['passed'] and all(matrix['gates'].values())
    assert len(matrix['checks'])==20
    assert all(c.get('repeat_count')==2 for c in matrix['checks'])


def test_unaffected_fields_are_behavior_gate():
    assert fm.preserves_unaffected({'attempts':1,'tools':[],'session':'s'}, {'attempts':3,'tools':['t'],'session':'s'}, [['attempts'],['tools']])
    assert not fm.preserves_unaffected({'attempts':1,'tools':[],'session':'wrong'}, {'attempts':3,'tools':['t'],'session':'s'}, [['attempts'],['tools']])


def test_independent_impact_can_refuse_model(client):
    j=modeled();value=g.asset(j,'fingerprint');value.update(review='conflict',review_reason='冻结条件未能准确表达文本设计，不能同意该影响范围。')
    with pytest.raises(handoff.NeedsReview,match='独立影响审核'):protocol.validate_faults(j,value)


def test_historical_classification_corpus():
    from pathlib import Path
    corpus=json.loads((Path(__file__).parent/'fixtures/fault_classification_regressions.json').read_text())
    for case in corpus['cases']:
        group='target' if fm.triggers({'trigger':corpus['trigger']},case['input']) else 'regression'
        assert group==case['required_group'],case
        assert group!=case['old_group']


def test_subtree_paths_and_invalid_paths():
    contract={'input_schema':{'type':'object','properties':{'ready':{'type':'boolean'}}},
              'output_schema':{'type':'object','properties':{'tools':{'type':'array','items':{'type':'string'}}}}}
    model={'trigger':{'any_of':[[{'path':['ready'],'quantifier':'value','operator':'eq','value':False}]]},'affected_paths':[['tools']]}
    fm.validate_model(model,contract)
    model['affected_paths']=[['missing']]
    with pytest.raises(ValueError,match='公开JSON接口'):fm.validate_model(model,contract)


def test_training_publication_does_not_expose_fault_model(client):
    j=modeled()
    assert 'fault_model' not in json.dumps(g.public(j))
    # Frozen bundle is in the author review digest asset list, not learner context.
    assert 'project_build' in g.review_keys(j)
    j['matrix']={'checks':[]}
    assert 'frozen_fault_model' not in roles.context(j,'teaching')
