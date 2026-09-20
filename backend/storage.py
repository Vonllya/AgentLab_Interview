import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / 'tasks'
DATA = Path(os.getenv('AGENTLAB_DATA', str(ROOT / 'data'))).resolve()
LOCK = threading.RLock()


def ident():
    return uuid.uuid4().hex


def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA / 'app.sqlite3', timeout=15)
    db.row_factory = sqlite3.Row
    return db


def init():
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS objects (kind TEXT, id TEXT PRIMARY KEY, session TEXT, body TEXT)')
    for path in TASKS.glob('*/1.0.0/manifest.json'):
        task = json.loads(path.read_text())
        task.pop('private_assets',None)
        put('task', task['id'], task)
    from .generation import recover
    recover()
    for path in sorted((DATA/'published').glob('gen_*/*/manifest.json'),key=lambda p:tuple(int(n) for n in p.parent.name.split('.'))):
        task=json.loads(path.read_text());put('task',task['id'],task)
    for run in all_objects('run'):
        if run['status'] in ('queued', 'running'):
            from .executor import cleanup_run
            folder = DATA / 'runs' / run['id']
            folder.mkdir(parents=True, exist_ok=True)
            (folder / 'cancelled').touch()
            run.update(status='interrupted', output='服务重启，原执行已中断。')
            put('run', run['id'], run, run['session'])
            cleanup_run(run['id'])

    for report in all_objects('report'):
        if report.get('feedback_status')=='generating':
            report.update(feedback_status='failed',feedback='',feedback_error={'category':'interrupted','reason':'服务重启，模型反馈生成已中断'})
            for attempt in report.get('feedback_attempts',[]):
                if attempt.get('status')=='running':attempt.update(status='failed',finished=time.time(),error=report['feedback_error'])
            put('report',report['id'],report,report['session'])


def put(kind, id, body, session=None):
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO objects VALUES (?,?,?,?)', (kind,id,session,json.dumps(body,ensure_ascii=False)))
    return body


def get(kind, id):
    with connect() as db:
        row = db.execute('SELECT body FROM objects WHERE kind=? AND id=?',(kind,id)).fetchone()
    if not row:
        raise KeyError(id)
    return json.loads(row['body'])


def all_objects(kind, session=None):
    with connect() as db:
        rows = db.execute('SELECT body FROM objects WHERE kind=?'+ (' AND session=?' if session else '') + ' ORDER BY rowid DESC', (kind,session) if session else (kind,)).fetchall()
    return [json.loads(row['body']) for row in rows]


def event(session, role, content, **extra):
    id = ident()
    return put('event',id,dict(id=id,session=session,time=time.time(),role=role,content=content,**extra),session)


def package(session):
    return (DATA/'published' if session['task_id'].startswith('gen_') else TASKS) / session['task_id'] / session['version']


def public_manifest(session):
    manifest=json.loads((package(session)/'manifest.json').read_text())
    manifest.pop('private_assets',None)
    return manifest
