"""Opt-in real-provider smoke via a normally configured running app; no secret reads."""
import json
import os
import time
from pathlib import Path
import httpx


def main():
    if os.getenv('AGENTLAB_REAL_SMOKE')!='1':
        raise SystemExit('Set AGENTLAB_REAL_SMOKE=1 to allow provider use')
    proof={}
    out=Path('data/v011-verification');out.mkdir(parents=True,exist_ok=True)
    with httpx.Client(base_url='http://127.0.0.1:8000/api',timeout=240) as client:
        def api(path,method='GET',data=None):
            response=client.request(method,path,json=data)
            response.raise_for_status();return response.json()
        def wait_run(id):
            deadline=time.monotonic()+110
            while time.monotonic()<deadline:
                run=api('/runs/'+id)
                if run['status'] not in ('queued','running'):return run
                time.sleep(.5)
            raise TimeoutError('Run did not reach terminal state')
        health=api('/health')
        assert health['agent_mode']=='real' and health['docker_available'],health
        session=api('/sessions','POST',{'task_id':'rag_versioning'});id=session['id'];url='/sessions/'+id
        proof['session']=id
        try:
            run=wait_run(api(url+'/runs','POST')['id']);proof['public_run']=run
            assert run['status']=='failed'
            assert any(c['id']=='version-update' and c['status']=='failed' for c in run['checks'])
            prompt=('请读取 pipeline.py、index_store.py 和 retrieval.py，结合最近公开测试（执行 '+run['id']+'）与公开诊断轨迹，做一次简短的跨模块调查：哪些是执行观察，哪些还只是代码推断？下一步验证什么？轨迹是否可以独立证明通过？不要直接提供完整修复代码，也不要超出已授权提示等级。')
            reply=api(url+'/chat','POST',{'message':prompt});proof['reply']=reply
            state=api(url);proof['tools']=[e for e in state['events'] if e['role']=='tool']
            assert reply.get('status')!='error',reply.get('error')
            reads={e.get('arguments',{}).get('path') for e in proof['tools'] if e['name']=='read_workspace_file' and e['status']=='ok'}
            assert len(reads)>=2,reads
            assert any(e['name'] in ('get_session_evidence','get_run_result') and e['status']=='ok' for e in proof['tools'])
            assert 'Mock' not in reply['content'] and '已拦截' not in reply['content']
            # This is a new submission, never a rewrite of existing training evidence.
            package=Path('tasks/rag_versioning/1.0.0/private/reference')
            files={name:(package/name).read_text() for name in state['permissions']['editable']}
            api(url+'/files','PUT',{'files':files,'diagnosis':'同一逻辑文档更新后仍有旧版本片段；采用文档范围替换，保留高版本门槛，验证其他文档、空正文、延迟低版本及重开后的持久化。'})
            submitted=wait_run(api(url+'/submit','POST')['id']);proof['submission']=submitted
            assert submitted['status']=='passed'
            deadline=time.monotonic()+100
            while time.monotonic()<deadline:
                reports=api(url)['reports']
                if reports and reports[0].get('feedback_status')!='generating':break
                time.sleep(.5)
            report=reports[0];proof['report']=report
            assert report['snapshot']==submitted['snapshot']==report['objective']['snapshot']
            proof['persisted']=api('/reports/'+report['id'])==report
            proof['completed']=True
            print(json.dumps({'session':id,'reply_id':reply['id'],'read_modules':sorted(reads),'report_id':report['id'],'feedback_status':report.get('feedback_status'),'feedback_error':report.get('feedback_error'),'persisted':proof['persisted']},ensure_ascii=False))
        finally:
            (out/'real-model.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
