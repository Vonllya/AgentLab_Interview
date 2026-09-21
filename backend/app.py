from contextlib import asynccontextmanager
import json
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from . import storage as s, workspace as w, runs, agent
from .executor import availability

@asynccontextmanager
async def lifespan(app):
    s.init()
    yield

app=FastAPI(title='AgentLab Interview',lifespan=lifespan)

@app.middleware('http')
async def local_only(request:Request,call_next):
    # Block browser cross-origin mutations and DNS rebinding; no permissive CORS.
    from starlette.responses import JSONResponse
    host=request.headers.get('host','').split(':')[0]
    origin=request.headers.get('origin')
    if host not in ('127.0.0.1','localhost','testserver') or (origin and origin not in ('http://127.0.0.1:5173','http://localhost:5173','http://127.0.0.1:8000','http://localhost:8000')):
        return JSONResponse({'detail':'仅允许本地同源访问'},status_code=403)
    return await call_next(request)

@app.exception_handler(KeyError)
async def missing(request,exc):
    from starlette.responses import JSONResponse
    return JSONResponse({'detail':'记录不存在'},status_code=404)

@app.exception_handler(ValueError)
async def invalid(request,exc):
    from starlette.responses import JSONResponse
    return JSONResponse({'detail':str(exc)},status_code=400)

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')
class Create(Strict):
    task_id:str=Field(pattern='^[a-z][a-z0-9_]{0,63}$')
class Save(Strict):
    code:str|None=Field(default=None,max_length=65536)
    files:dict[str,str]|None=None
    diagnosis:str=Field(default='',max_length=10000)
class Chat(Strict):
    message:str=Field(min_length=1,max_length=6000)

@app.get('/api/health')
def health():
    ready,reason=availability()
    return dict(agent_mode=agent.mode(),docker_available=ready,reason=reason)

@app.get('/api/tasks')
def tasks(): return sorted(s.all_objects('task'),key=lambda task:({'rag':0,'retry':1,'resume':2,'rag_versioning':3}.get(task['id'],4),task['id']))

@app.get('/api/sessions')
def sessions(): return s.all_objects('session')

@app.post('/api/sessions')
def create(body:Create): return w.create(body.task_id)

@app.get('/api/sessions/{id}')
def session(id:str):
    obj=s.get('session',id)
    return dict(**obj,task=s.public_manifest(obj),code=w.read(obj),files=w.read_all(obj),permissions=w.permissions(obj),events=list(reversed(s.all_objects('event',id))),runs=s.all_objects('run',id),reports=s.all_objects('report',id),hints=list(reversed(s.all_objects('hint',id))))

@app.put('/api/sessions/{id}/files')
def save(id:str,body:Save):
    with s.LOCK:
        obj=s.get('session',id)
        if (body.code is None)==(body.files is None): raise ValueError('请提供 code 或 files 之一')
        w.save_files(obj,body.files if body.files is not None else {'solution.py':body.code},body.diagnosis)
    return {'saved':True}

@app.get('/api/sessions/{id}/files')
def files(id:str,path:str='solution.py'):
    return {'path':path,'content':w.safe_file(s.get('session',id),path).read_text()}

@app.get('/api/sessions/{id}/public-tests')
def public_tests(id:str):
    p=s.package(s.get('session',id))
    return {'test':(p/'public_test.py').read_text(),'cases':json.loads((p/'public_cases.json').read_text())}

@app.post('/api/sessions/{id}/runs')
def run(id:str): return runs.start(s.get('session',id),'public')

@app.post('/api/sessions/{id}/submit')
def submit(id:str): return runs.start(s.get('session',id),'submission')

@app.get('/api/runs/{id}')
def get_run(id:str): return s.get('run',id)

@app.get('/api/reports/{id}')
def report(id:str): return s.get('report',id)

@app.get('/api/sessions/{id}/snapshots/{snapshot}')
def snapshot(id:str,snapshot:str):
    if not any(r['snapshot']==snapshot for r in s.all_objects('run',id)):
        raise HTTPException(404,'此会话没有该快照')
    obj=s.get('session',id)
    contents=w.snapshot_contents(obj,snapshot)
    return {'snapshot':snapshot,'code':contents['solution.py'],'files':contents,'task_id':obj['task_id'],'version':obj['version']}

@app.post('/api/sessions/{id}/hint')
def hint(id:str):
    obj=s.get('session',id)
    result=agent.hint(obj)
    s.event(id,'assistant',f"提示 {result['level']}/3：{result['text']}",hint_id=result['id'])
    return result

@app.post('/api/sessions/{id}/chat')
def chat(id:str,body:Chat): return agent.chat(s.get('session',id),body.message)

# Authoring routes are separate from training tools and file APIs.
from . import generation as g
from .generation_schema import Request as GenerationRequest, Contract

class ConfirmContract(Strict):
    version:int
    simulation_confirmed:bool=False
class Publish(Strict):
    approved:bool
    note:str=Field(min_length=10,max_length=2000)
    review_digest:str=Field(pattern='^[a-f0-9]{64}$')

@app.get('/api/generation/jobs')
def generation_jobs():return [g.public(j) for j in s.all_objects('generation')]

@app.post('/api/generation/jobs')
def generation_create(body:GenerationRequest):return g.public(g.create(body,direct_build=True,handoff=True))

@app.get('/api/generation/jobs/{id}')
def generation_job(id:str):return g.public(g.get(id))

@app.post('/api/generation/jobs/{id}/analyze')
def generation_analyze(id:str):return g.analyze(id)

@app.put('/api/generation/jobs/{id}/contract')
def generation_contract(id:str,body:Contract):return g.revise(id,body)

@app.post('/api/generation/jobs/{id}/confirm')
def generation_confirm(id:str,body:ConfirmContract):return g.confirm(id,body.version,body.simulation_confirmed)

@app.post('/api/generation/jobs/{id}/retry')
def generation_retry(id:str):return g.retry(id)

@app.post('/api/generation/jobs/{id}/cancel')
def generation_cancel(id:str):return g.cancel(id)

@app.get('/api/author/generation/{id}')
def generation_review(id:str):return g.review_assets(id)

@app.post('/api/author/generation/{id}/publish')
def generation_publish(id:str,body:Publish):return g.publish(id,body.approved,body.note,body.review_digest)


@app.post('/api/author/generation/{id}/new-version')
def generation_new_version(id:str):return g.fork(id)


class ContractClarification(Strict):
    reason:str=Field(min_length=10,max_length=2000)

@app.post('/api/generation/jobs/{id}/reanalyze')
def generation_reanalyze(id:str,body:ContractClarification):return g.reanalyze(id,body.reason)


@app.post('/api/author/generation/{id}/repair-evaluation')
def generation_repair_evaluation(id:str,body:ContractClarification):return g.repair_evaluation(id,body.reason)


from .generation_budget import BudgetPolicy
class Regenerate(Strict):
    expected_revision:int=Field(ge=0)
    idempotency_key:str=Field(pattern='^[a-zA-Z0-9_-]{8,80}$')
    repair_note:str=Field(default='',max_length=2000)
    new_batch:bool=False
    budget:BudgetPolicy|None=None

@app.post('/api/generation/jobs/{id}/regenerate')
def generation_regenerate(id:str,body:Regenerate):
    from .generation_flow import regenerate
    return regenerate(id,body)


from typing import Annotated
class RequirementAnswer(Strict):
    expected_revision:int=Field(ge=0)
    question_id:str=Field(pattern='^[a-f0-9]{32}$')
    answers:dict[str,Annotated[str,Field(min_length=1,max_length=2000)]]=Field(min_length=1,max_length=3)

@app.post('/api/generation/jobs/{id}/requirement-answer')
def generation_requirement_answer(id:str,body:RequirementAnswer):
    from .contract_revision import answer
    return answer(id,body)
