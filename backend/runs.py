import json
import os
import subprocess
import sys
import threading
import time
from . import storage as s, workspace as w
from .executor import availability, cleanup_run

POOL=threading.BoundedSemaphore(2)


def start(session, kind):
    ok,reason=availability()
    if not ok:
        raise ValueError(reason)
    with s.LOCK:
        if any(r['status'] in ('queued','running') for r in s.all_objects('run',session['id'])):
            raise ValueError('本会话已有执行，请等待完成')
        if not POOL.acquire(blocking=False):
            raise ValueError('执行资源已满，请稍后重试')
        try:
            snap=w.snapshot(session)
            id=s.ident()
            run=dict(id=id,session=session['id'],snapshot=snap,kind=kind,status='queued',created=time.time(),duration=None,exit_code=None,output='',checks=[],diagnosis=session['diagnosis'],hints=s.all_objects('hint',session['id']))
            s.put('run',id,run,session['id'])
            threading.Thread(target=perform,args=(session,run),daemon=True).start()
            return run
        except Exception:
            POOL.release()
            raise


def perform(session,run):
    started=time.monotonic()
    proc=None
    try:
        run['status']='running'
        s.put('run',run['id'],run,session['id'])
        folder=s.DATA/'runs'/run['id']; folder.mkdir(parents=True)
        snap=s.DATA/'snapshots'/run['snapshot']
        violations=w.constraints(session,(snap/'solution.py').read_text())
        if violations:
            run.update(status='failed',exit_code=1,checks=[dict(id='constraint',group='constraint',visibility='public',status='failed',detail='；'.join(violations))],output='修改范围不符合任务约束')
        else:
            cases=json.loads((s.package(session)/'public_cases.json').read_text())
            for case in cases: case['visibility']='public'
            if run['kind']=='submission':
                hidden=json.loads((s.package(session)/'private/hidden_cases.json').read_text())
                for case in hidden: case['visibility']='hidden'
                cases+=hidden
            config=folder/'config.json'; results=folder/'checks.jsonl'
            config.write_text(json.dumps(dict(cases=cases,snapshot_dir=str(snap),results=str(results),cancel_file=str(folder/'cancelled'))))
            env={k:v for k,v in os.environ.items() if k not in ('MODEL_API_KEY',)}
            env['AGENTLAB_GRADE_CONFIG']=str(config)
            env['AGENTLAB_RUN_ID']=run['id']
            # pytest output stays server-side and never leaks hidden assertions.
            with (folder/'pytest.log').open('w') as out:
                proc=subprocess.Popen([sys.executable,'-m','pytest',str(s.ROOT/'backend/grade_suite.py'),'-q','--tb=no','-p','no:cacheprovider'],cwd=s.ROOT,env=env,stdout=out,stderr=out)
                try:
                    run['exit_code']=proc.wait(timeout=100)
                except subprocess.TimeoutExpired:
                    (folder/'cancelled').touch()
                    proc.kill(); proc.wait()
                    run['status']='timeout'
            if results.exists():
                run['checks']=[json.loads(line) for line in results.read_text().splitlines()]
            if run['status']!='timeout':
                complete = len(run['checks']) == len(cases)
                if not complete or any(c['status']=='error' for c in run['checks']):
                    run['status']='error'
                else:
                    run['status']='passed' if run['exit_code']==0 and all(c['status']=='passed' for c in run['checks']) else 'failed'
            if any(c['status']=='timeout' for c in run['checks']): run['status']='timeout'
            run['output']=f"已完成 {len(run['checks'])}/{len(cases)} 项可信行为检查；"+ ('全部通过' if run['status']=='passed' else '存在失败、错误或未完成检查')
            run['checks'].append(dict(id='modification-scope',group='constraint',visibility='public',status='passed',detail='仅执行允许的 solution.py；受保护函数外代码与原任务一致。' if session['task_id']!='rag' else '仅执行允许的 solution.py；重排与过滤约束由行为检查验证。'))
    except Exception as exc:
        run.update(status='error',output=f'执行器错误：{type(exc).__name__}: {str(exc)[:300]}')
    finally:
        cleanup_run(run['id'])
        run['duration']=round(time.monotonic()-started,3)
        s.put('run',run['id'],run,session['id'])
        POOL.release()
        if run['kind']=='submission':
            report=dict(id=s.ident(),session=session['id'],run_id=run['id'],snapshot=run['snapshot'],created=time.time(),diagnosis=run['diagnosis'],objective=run.copy(),feedback='',feedback_status='generating')
            s.put('report',report['id'],report,session['id'])
            with s.LOCK:
                current=s.get('session',session['id']); current['status']='submitted'; s.put('session',session['id'],current)
            from .agent import report_feedback
            report_feedback(session,report)
