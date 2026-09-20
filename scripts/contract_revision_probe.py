"""Two-call real contract-only smoke test on a constructed public fixture, never publishes."""
import json,os
from pathlib import Path
if os.getenv('AGENTLAB_REAL_SMOKE')!='1':raise SystemExit('Requires AGENTLAB_REAL_SMOKE=1')
from backend import generation as g,generation_flow as f,generation_budget as b,contract_revision as c,storage as s,agent
from backend.generation_schema import Request
from backend.generation_mock import response
assert str(s.DATA).endswith('/contract-revision-probe') and agent.mode()=='real'
s.init()
requirement='训练整数累加：返回所有整数的算术和，包括负数；空列表返回0。输入values为最多20个绝对值小于100的整数；只使用本地Python标准库。'
job=g.create(Request(requirement=requirement))
contract=response('design',{})['contract']
contract.update(title='局部契约修订人工构造样例',scenario='对本地整数列表进行累加，调查负数参与计算时出现的偏差。',capabilities=['边界验证'],simulation='本地确定性计算，不使用真实外部服务。')
contract['behaviors']['sum']='只累加正数，忽略负数'
job.update(contract=contract,contract_hash=g.digest(contract),contract_version=1,confirmed_version=1,budget=b.initialize(b.BudgetPolicy(requests=2)),contract_issue={'behavior_ids':['sum'],'category':'contract','evaluation_action':'none'})
g.put(job);b.begin(job)
result={'fixture':'人工构造公开契约转述错误；非旧失败输入复现、非完整项目生成','id':job['id'],'request_limit':2,'passed':False}
try:
 proposal=f.call(job,'contract_review');check=f.call(job,'contract_check')
 result.update(proposal=proposal,check=check)
 if proposal['decision']=='correction' and check['verdict']=='approve':
  before=dict(job['contract']);stage=c.apply(job)
  result.update(next_stage=stage,version=job['contract_version'],corrected_behaviors=job['contract']['behaviors'])
  result['passed']=stage=='build' and job['contract_version']==2 and [p['path'] for p in proposal['changes']]==['/behaviors/sum'] and all(job['contract'][k]==v for k,v in before.items() if k!='behaviors')
except Exception as exc:result['error']={'type':type(exc).__name__,'reason':str(exc)[:1000]}
finally:
 b.end(job);job['status']='interrupted';g.put(job)
 result.update(requests=job['request_count'],attempts=[{k:a.get(k) for k in ('stage','status','metadata','input_hash','output_hash')} for a in job['attempts']])
 folder=Path('data/contract-revision-verification');folder.mkdir(exist_ok=True,parents=True)
 (folder/('provider-'+job['id']+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps(result,ensure_ascii=False,indent=2))
raise SystemExit(0 if result['passed'] else 1)
