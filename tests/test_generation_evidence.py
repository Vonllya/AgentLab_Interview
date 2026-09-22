import copy
import pytest
from backend import generation as g, generation_evidence as e, generation_handoff as h, generation_roles as roles
from test_handoff import prepared,order


def ready():
 j=prepared();j['matrix']['contract_hash']=j['contract_hash']
 build=g.asset(j,'build');versions={k:build[k] for k in ('normal','faulty','reference')};versions.update(build['evasions'])
 for c in j['matrix']['checks']:c['snapshot']=g.digest(versions[c['version']])
 g.put(j);return j


def test_existing_evidence_no_execution_and_ack(client,monkeypatch):
 j=ready();check=j['matrix']['checks'][0]
 monkeypatch.setattr(g.executor,'execute',lambda *a,**kw:pytest.fail('must reuse'))
 r=e.resolve(j,{'requests':[{'kind':'file','variant':'faulty','path':'app.py','question':'核对入口是否等待'}, {'kind':'check','check_id':check['id'],'question':'确认已执行的结果'}]})
 assert r['status']=='completed' and r['results'][0]['code']==g.asset(j,'build')['faulty']['app.py']
 assert r['results'][1]['execution']['id']==check['id'] and j['budget']['validations']==0
 assert roles.context(j,'diagnosis')['diagnostic_evidence'][0]['id']==r['id']
 assert 'diagnostic_evidence' not in roles.context(j,'evaluation')
 assert 'diagnostic_evidence' not in g.public(j)
 with pytest.raises(ValueError,match='逐项'):h.validate_order(j,order(j))
 p=order(j);p['evidence_responses']={r['id']:'已确认代码和执行结果，下一步仅修复尚未满足的回归义务。'}
 assert h.validate_order(j,p)


def test_repeated_bounded_and_stale(client):
 j=ready();action={'requests':[{'kind':'file','variant':'faulty','path':'app.py','question':'确认文件内容'}]}
 e.resolve(j,action);r=e.resolve(j,action)
 assert r['results'][0]['status']=='already_provided'
 with pytest.raises(e.EvidenceStop,match='两轮'):e.resolve(j,action)
 j['contract_hash']='changed';assert e.current(j)==[]


def test_paths_and_unsupported_requests(client):
 j=ready()
 for path in ['../secret.py','/app.py','solution.py','hidden.py']:
  with pytest.raises(e.EvidenceStop):e.resolve(j,{'requests':[{'kind':'file','variant':'faulty','path':path,'question':'读取指定业务文件'}]})
 with pytest.raises(e.EvidenceStop):e.resolve(j,{'requests':[{'kind':'check','check_id':'old-matrix','question':'读取旧的执行结果'}]})
 from pydantic import TypeAdapter,ValidationError
 with pytest.raises(ValidationError):TypeAdapter(e.EvidenceRequest).validate_python({'kind':'scenario','variant':'faulty','case_id':'case','question':'验证入口调用','shell':'evil'})


def test_experiment_error_budget_and_snapshot(client,monkeypatch):
 j=ready();j['matrix']['environment']='sha256:'+'a'*64
 c=g.asset(j,'evaluation')['cases'][0];j['matrix']['checks']=[];g.put(j)
 monkeypatch.setattr(g.executor,'availability',lambda:(True,''))
 def run(folder,payload,**kw):
  assert kw['image_id']==j['matrix']['environment'] and payload==c['input']
  assert set(p.name for p in folder.iterdir())==set(j['contract']['files'])|{'solution.py'}
  raise TimeoutError('fixture timeout')
 monkeypatch.setattr(g.executor,'execute',run)
 r=e.resolve(j,{'requests':[{'kind':'scenario','variant':'faulty','case_id':c['id'],'question':'核对固定输入'}]})
 assert r['results'][0]['status']=='error' and j['budget']['validations']==1
 assert not j['matrix'].get('passed')
 j['budget']['policy']['validations']=1
 with pytest.raises(e.EvidenceStop):e.resolve(j,{'requests':[{'kind':'scenario','variant':'normal','case_id':c['id'],'question':'核对另一个版本'}]})


def test_actual_docker_diagnostic(client):
 import subprocess
 j=ready();ok,reason=g.executor.availability()
 if not ok:pytest.skip(reason)
 j['matrix']['environment']=subprocess.check_output(['docker','image','inspect',g.executor.IMAGE,'--format','{{.Id}}'],text=True).strip()
 j['matrix']['checks']=[];g.put(j);c=g.asset(j,'evaluation')['cases'][0]
 r=e.resolve(j,{'requests':[{'kind':'scenario','variant':'normal','case_id':c['id'],'question':'验证正常固定场景'}]})
 assert r['results'][0]['status']=='observed' and r['results'][0]['actual']==c['expected']
 assert j['matrix']['checks']==[] and j['matrix']['passed'] is False


def test_restart_marks_experiment_interrupted(client):
 j=ready();j['status']='probing_evidence';j['diagnostic_evidence']=[{'id':'probe','binding':e.binding(j),'status':'gathering','results':[{'status':'running'}]}];g.put(j)
 g.recover();saved=g.get(j['id'])
 assert saved['status']=='interrupted' and saved['diagnostic_evidence'][0]['results'][0]['status']=='interrupted'


def test_coordinator_returns_to_diagnosis(client,monkeypatch):
 from backend import generation_flow as f
 j=ready();seen=[]
 def call(job,stage):
  assert stage=='diagnosis';seen.append(stage)
  if len(seen)>1:
   assert e.current(job)[0]['results'][0]['code']
   raise h.NeedsReview('fixture ends after evidence return')
  p=order(job);p['action']={'kind':'need_evidence','missing':'需要确认故障入口实际是否等待后端就绪。','proposed_verification':'读取当前故障版本入口代码并核对既有调用。','requests':[{'kind':'file','variant':'faulty','path':'app.py','question':'确认故障入口调用'}]}
  return h.validate_order(job,p)
 monkeypatch.setattr(f,'call',call)
 assert g.POOL.acquire(blocking=False)
 f.run(j['id'],'diagnosis')
 assert len(seen)==2 and g.get(j['id'])['diagnostic_evidence'][0]['status']=='completed'


def test_interrupted_resume_does_not_repeat_completed_request(client,monkeypatch):
 from backend import generation_flow as f
 j=ready();e.resolve(j,{'requests':[{'kind':'file','variant':'faulty','path':'app.py','question':'确认入口业务代码'}]})
 j.update(status='interrupted',checkpoint='diagnosis',diagnoses=[{'work_order':{'action':{'kind':'need_evidence'}}}])
 j['attempts'].append({'stage':'diagnosis','status':'completed'});g.put(j)
 monkeypatch.setattr(g,'launch',lambda id,stage:stage)
 assert f.resume(j['id'])=='diagnosis'
 assert 'completed_diagnosis' not in g.get(j['id'])
