"""Offline browser fixture for a pending contract clarification, never production data."""
import os
from backend import generation as g, storage as s
from backend.generation_schema import Request
from backend.generation_mock import response
assert os.getenv('AGENT_MODE')=='mock' and str(s.DATA).startswith('/tmp/agentlab-')
job=g.create(Request(requirement='MOCK 离线契约澄清流程；不证明模型能判断需求语义。'))
design=response('design',{})
job.update(contract=design['contract'],contract_version=1,confirmed_version=1,contract_hash=g.digest(design['contract']),assessment='simulation',private_fault_requirements=design['private_fault_requirements'],status='interrupted',checkpoint='contract_review',stage='contract_review')
g.put(job)
print(job['id'])
