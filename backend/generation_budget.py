"""Shared conservative accounting for all generation roles (never training chat/report)."""
import time
from pydantic import Field
from .generation_schema import Strict

POLICY='roles-v1'
ROLE_LIMITS={'project_build':12000,'spec_review':4000,'design':4000,'build':12000,'evaluation':6000,'fingerprint':3000,'diagnosis':3000,'repair_build':12000,'teaching':3000,'contract_review':4000,'contract_check':3000}
class BudgetPolicy(Strict):
    requests:int=Field(default=24,ge=1,le=24)
    output_tokens:int=Field(default=96000,ge=512,le=96000)
    input_bytes:int=Field(default=600000,ge=1000,le=600000)
    seconds:int=Field(default=1200,ge=10,le=1200)
    validations:int=Field(default=10,ge=1,le=10)
class Exhausted(ValueError):pass

def initialize(policy=None):
    return {'policy':(policy or BudgetPolicy()).model_dump(),'requests':0,'output_charged':0,'input_bytes':0,'validations':0,'active_seconds':0,'unknown_usage':0}

def remaining(job):
    b=job['budget'];active=time.time()-b['active_started'] if b.get('active_started') else 0
    return max(0,b['policy']['seconds']-b['active_seconds']-active)

def begin(job):job['budget']['active_started']=time.time()
def end(job):
    b=job['budget'];start=b.pop('active_started',None)
    if start is not None:b['active_seconds']+=max(0,time.time()-start)

def reserve(job,role,input_bytes):
    b=job['budget'];p=b['policy'];left=p['output_tokens']-b['output_charged']
    if b['requests']>=p['requests']:raise Exhausted('本批模型请求次数预算耗尽')
    if left<512:raise Exhausted('本批剩余输出额度不足512 Token，预算耗尽')
    if b['input_bytes']+input_bytes>p['input_bytes']:raise Exhausted(f'本批输入字节预算不足：已用{b["input_bytes"]}，下一次需要{input_bytes}，上限{p["input_bytes"]}')
    if remaining(job)<=0:raise Exhausted('本批活动执行时间预算耗尽')
    cap=min(ROLE_LIMITS[role],left)
    b['requests']+=1;b['input_bytes']+=input_bytes;b['output_charged']+=cap
    return cap

def settle(job,attempt,metadata):
    b=job['budget'];usage=(metadata or {}).get('usage') or {};used=usage.get('completion_tokens')
    if type(used) is int and 0<=used<=attempt['reserved_tokens']:
        b['output_charged']-=attempt['reserved_tokens']-used;attempt['charged_tokens']=used
    else:
        b['unknown_usage']+=1;attempt['charged_tokens']=attempt['reserved_tokens'];attempt['usage_unknown']=True

def validation(job):
    b=job['budget']
    if b['validations']>=b['policy']['validations'] or remaining(job)<=0:raise Exhausted('本批实际验证次数或执行时间预算耗尽')
    b['validations']+=1
