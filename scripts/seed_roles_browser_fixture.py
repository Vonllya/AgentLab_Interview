"""Test-only fixture: actual Docker failure, deliberately spent offline budget."""
import json,os
from pathlib import Path
from backend import generation as g, storage as s, generation_budget as b
from backend.generation_schema import Request
assert os.getenv('AGENT_MODE')=='mock' and str(s.DATA).startswith('/tmp/agentlab-'), 'Only isolated mock test data permitted'
s.init()
job=g.create(Request(requirement='MOCK 浏览器自动修复验收，非真实生成'),policy=False)
design=g.model_stage(job,'design')
job.update(contract=design['contract'],contract_version=1,confirmed_version=1,contract_hash=g.digest(design['contract']),assessment='simulation',private_fault_requirements=design['private_fault_requirements'])
g.put(job);project=g.model_stage(job,'build');g.model_stage(job,'evaluation')
project['faulty']=dict(project['normal']);project['faulty']['calculator.py']+='\n# deliberately equivalent faulty candidate\n'
(g.root(job)/job['assets']['build']/'output.json').write_text(json.dumps(project))
try:g.validate(job)
except ValueError:pass
assert job['matrix'] and not job['matrix']['gates']['fault_trigger'] and job['matrix']['gates']['no_runtime_errors']
job.update(policy_version=b.POLICY,batch_id=job['id'],budget=b.initialize(b.BudgetPolicy(requests=1)),status='budget_exhausted',checkpoint='diagnosis',revision=0,error={'category':'budget_exhausted','reason':'MOCK 测试夹具的已消费预算；矩阵由实际 Docker 执行'})
job['budget']['requests']=1;g.put(job)
print(job['id'])
