"""One real builder call and one isolated Docker matrix from a saved failed handoff."""
import copy,json,os,shutil,sqlite3
from pathlib import Path


def main():
    assert os.getenv('AGENTLAB_REAL_SMOKE')=='1'
    root=Path(__file__).resolve().parents[1];source_id='1df4672d36704837baf7a58db35ccafb'
    db=sqlite3.connect(root/'data/app.sqlite3');source=json.loads(db.execute('select body from objects where id=?',(source_id,)).fetchone()[0]);db.close()
    os.environ['AGENTLAB_DATA']=str(root/'data/delivery-verification/real-isolated')
    from backend import generation as g,storage as s,generation_flow as flow,generation_budget as budget,agent
    assert agent.mode()=='real';s.init()
    job=copy.deepcopy(source);job.update(id=s.ident(),attempts=[],request_count=0,validation_count=0,status='interrupted',checkpoint='repair_build',error=None)
    for k in ('coordinator_token','active_action','format_error'):job.pop(k,None)
    job['budget']=budget.initialize(budget.BudgetPolicy(requests=1,output_tokens=12000,seconds=240,validations=1))
    refs=set(job['assets'].values())|set(job.get('candidate_assets',{}).values())
    for ref in refs:shutil.copytree(root/'data/generation'/source_id/ref,g.root(job)/ref)
    g.put(job);print(json.dumps({'id':job['id'],'source':source_id,'max_requests':1}),flush=True)
    budget.begin(job)
    try:
        result=flow.call(job,'repair_build')
        if result.get('handoff_return'):job.update(status='needs_manual_review',checkpoint='diagnosis')
        else:
            budget.validation(job);g.validate(job)
            job.update(status='interrupted',checkpoint='teaching')  # No teaching or publication in this probe.
    except Exception as exc:job.update(status='failed',error={'category':getattr(exc,'category',type(exc).__name__),'reason':str(exc)[:1800]})
    finally:budget.end(job);g.put(job)
    result={'id':job['id'],'status':job['status'],'error':job.get('error'),'requests':job['request_count'],
            'matrix_id':job.get('matrix',{}).get('id'),'gates':job.get('matrix',{}).get('gates'),
            'new_matrix':job.get('matrix',{}).get('id')!=source['matrix']['id']}
    (s.DATA.parent/(job['id']+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
