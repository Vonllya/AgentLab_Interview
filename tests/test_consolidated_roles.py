import json
from backend import generation as g, generation_roles as roles, generation_flow as f
from backend.generation_schema import Request
from test_generation_direct import built


def test_new_role_ownership_and_historical_compatibility(client):
    j=built()
    assert roles.identity(j,'project_build')['role_id']==roles.identity(j,'repair_build')['role_id']=='builder'
    assert {roles.identity(j,k)['role_id'] for k in ('spec_review','evaluation','fingerprint','diagnosis')}=={'evaluator'}
    assert roles.identity(j,'teaching')['role_id']=='teacher'
    assert j['attempts'][0]['role_policy']==roles.ROLE_POLICY
    assert g.public(j)['attempts'][0]['role_id']=='builder'
    legacy=g.create(Request(requirement='MOCK 旧角色兼容测试'))
    assert roles.identity(legacy,'diagnosis')['role']=='失败诊断 Agent'
    assert 'role_id' not in roles.identity(legacy,'diagnosis')


def test_evaluator_stage_boundaries_and_latest_evidence(client):
    j=built();f.call(j,'evaluation');f.call(j,'fingerprint')
    j['private_fault_requirements']='PRIVATE_DESIGN_SENTINEL';j['diagnoses']=[{'change_request':'OLD_PLAN_SENTINEL'}]
    j['matrix']={'id':'current-matrix','gates':{'fault_trigger':False,'evasion_rejected':True},'checks':[]}
    for stage in ('spec_review','evaluation'):
        encoded=json.dumps(roles.context(j,stage))
        assert 'PRIVATE_DESIGN_SENTINEL' not in encoded and 'def total' not in encoded
    fp=roles.context(j,'fingerprint')
    assert fp['private_fault_requirements']=='PRIVATE_DESIGN_SENTINEL'
    assert 'expected' not in json.dumps(fp) and 'def total' not in json.dumps(fp)
    diagnosis=roles.context(j,'diagnosis')
    assert diagnosis['failed_gates']==['fault_trigger']
    assert diagnosis['private_fault_requirements']=='PRIVATE_DESIGN_SENTINEL'
    assert 'OLD_PLAN_SENTINEL' not in json.dumps(diagnosis)
    assert 'project' in diagnosis and 'matrix' in diagnosis
    assert 'OLD_PLAN_SENTINEL' in json.dumps(j['diagnoses'])  # Audit retained.


def test_builder_work_order_preserves_fault_without_hidden_assets(client):
    j=built();f.call(j,'evaluation')
    j['pending_plan']={'matrix_id':'latest','contract_hash':j['contract_hash'],'target_variants':['faulty'],'category':'implementation','contract_behavior_ids':['sum'],'change_request':'DO_NOT_FORWARD_PRIVATE_PROSE'}
    j['matrix']={'checks':[{'case':'empty','visibility':'hidden','version':'faulty','actual':'HIDDEN_OUTPUT_SENTINEL'}]}
    ctx=roles.context(j,'repair_build');order=ctx['work_order']
    assert set(order['targets'])=={'faulty'} and '修正故障注入实现' in order['targets']['faulty'] and '不得消除指定故障' in order['targets']['faulty']
    assert order['matrix_id']=='latest'
    assert 'DO_NOT_FORWARD_PRIVATE_PROSE' not in json.dumps(ctx) and 'HIDDEN_OUTPUT_SENTINEL' not in json.dumps(ctx)
    for stage in ('project_build','repair_build'):
        assert '统一负责规范设计、项目构建和受限代码修复' in roles.messages(j,stage)[0]['content']
