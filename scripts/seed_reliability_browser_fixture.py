"""Explicit mock UI fixture with actual Docker failure evidence for retained author summary."""
import json,os
from backend import generation as g, generation_flow as f, generation_mock as mock, storage as s
from backend.generation_schema import Request
assert os.getenv('AGENT_MODE')=='mock' and str(s.DATA).startswith('/tmp/agentlab-')
s.init();job=g.create(Request(requirement='MOCK 失败证据与作者摘要浏览器功能验收'))
design=mock.response('design',{})
job.update(contract=design['contract'],contract_hash=g.digest(design['contract']),contract_version=1,confirmed_version=1,private_fault_requirements=design['private_fault_requirements']);g.put(job)
f.call(job,'build');f.call(job,'evaluation');f.call(job,'fingerprint')
p=g.asset(job,'build');p['evasions'][next(iter(p['evasions']))]=p['normal']
(g.root(job)/job['assets']['build']/'output.json').write_text(json.dumps(p))
try:g.validate(job)
except ValueError:pass
assert not job['matrix']['passed'] and job['matrix']['gates']['no_runtime_errors']
job.update(status='failed',error={'category':'validation','reason':'MOCK 浏览器夹具：实际规避检查未通过，不得发布'})
job['checkpoint']='diagnosis';g.put(job);print(job['id'])
