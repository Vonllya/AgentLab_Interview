"""One bounded real amendment of saved assets, never publication or source mutation."""
import copy,json,os,shutil,sqlite3
from pathlib import Path

def main():
    assert os.getenv('AGENTLAB_REAL_SMOKE')=='1'
    root=Path(__file__).resolve().parents[1];source_id='90a606ae6bc14db5afec84166838d42a'
    db=sqlite3.connect(root/'data/app.sqlite3');source=json.loads(db.execute('select body from objects where id=?',(source_id,)).fetchone()[0]);db.close()
    os.environ['AGENTLAB_DATA']=str(root/'data/spec-patch-verification/real-isolated')
    from backend import generation as g,storage as s,generation_flow as flow,generation_direct as direct,generation_budget as b,agent,generation_spec_patch as sp
    from backend.generation_schema import Request
    assert agent.mode()=='real'
    s.init();j=g.create(Request.model_validate(source['request']),direct_build=True,handoff=True,fault_model=True)
    for k in ('contract','contract_hash','contract_version','confirmed_version','private_fault_requirements','assets','installed_bundle','spec_review_feedback','assessment','rationale'):
        if k in source:j[k]=copy.deepcopy(source[k])
    for ref in set(j['assets'].values()):shutil.copytree(root/'data/generation'/source_id/ref,g.root(j)/ref)
    j['budget']=b.initialize(b.BudgetPolicy(requests=2,output_tokens=16000,seconds=240,validations=1));g.put(j)
    before=sp.current_bundle(j);print(json.dumps({'id':j['id'],'source':source_id,'max_requests':2}),flush=True)
    b.begin(j)
    try:
        flow.call(j,'project_build');after=g.asset(j,'project_build')
        assert {k:v for k,v in after.items() if k!='contract'}=={k:v for k,v in before.items() if k!='contract'}
        direct.install_bundle(j);flow.call(j,'spec_review');stage=direct.apply_review(j)
        if stage:j.update(status='interrupted',checkpoint=stage)
    except Exception as exc:
        j.update(status='needs_manual_review',error={'category':getattr(exc,'category',type(exc).__name__),'reason':str(exc)[:1800]})
    finally:b.end(j);g.put(j)
    out={k:j.get(k) for k in ('id','status','error','checkpoint','contract_version','request_count','spec_patch_conflict','spec_review_feedback')}
    out['attempts']=[{k:a.get(k) for k in ('stage','status','specification_patch','metadata','error')} for a in j['attempts']]
    out['frozen_unchanged']=all(g.asset(j,'project_build')[k]==before[k] for k in ('project','private_fault_requirements','fault_model'))
    (s.DATA.parent/(j['id']+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps({k:out[k] for k in ('id','status','error','request_count','frozen_unchanged')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
