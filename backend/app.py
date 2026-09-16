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
    task_id:str=Field(pattern='^(rag|retry|resume)$')
class Save(Strict):
    code:str=Field(max_length=65536)
    diagnosis:str=Field(default='',max_length=10000)
class Chat(Strict):
    message:str=Field(min_length=1,max_length=6000)

@app.get('/api/health')
def health():
    ready,reason=availability()
    return dict(agent_mode=agent.mode(),docker_available=ready,reason=reason)

@app.get('/api/tasks')
def tasks(): return sorted(s.all_objects('task'),key=lambda task:['rag','retry','resume'].index(task['id']))

@app.get('/api/sessions')
def sessions(): return s.all_objects('session')

@app.post('/api/sessions')
def create(body:Create): return w.create(body.task_id)

@app.get('/api/sessions/{id}')
def session(id:str):
    obj=s.get('session',id)
    return dict(**obj,code=w.read(obj),events=list(reversed(s.all_objects('event',id))),runs=s.all_objects('run',id),reports=s.all_objects('report',id),hints=list(reversed(s.all_objects('hint',id))))

@app.put('/api/sessions/{id}/files')
def save(id:str,body:Save):
    with s.LOCK:
        obj=s.get('session',id); w.save(obj,body.code,body.diagnosis)
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
    return {'snapshot':snapshot,'code':(s.DATA/'snapshots'/snapshot/'solution.py').read_text()}

@app.post('/api/sessions/{id}/hint')
def hint(id:str):
    obj=s.get('session',id)
    result=agent.hint(obj)
    s.event(id,'assistant',f"提示 {result['level']}/3：{result['text']}",hint_id=result['id'])
    return result

@app.post('/api/sessions/{id}/chat')
def chat(id:str,body:Chat): return agent.chat(s.get('session',id),body.message)
