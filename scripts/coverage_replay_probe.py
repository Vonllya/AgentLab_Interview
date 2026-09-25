"""Opt-in bounded real replay of one saved pre-execution coverage failure."""
import copy,json,os,shutil,sqlite3,time
from pathlib import Path

def main():
    assert os.getenv('AGENTLAB_REAL_SMOKE')=='1','Explicit real probe required'
    root=Path(__file__).resolve().parents[1];source_id='98ab434e09ea44e29dee402263eaa45c'
    db=sqlite3.connect(root/'data/app.sqlite3')
    source=json.loads(db.execute('select body from objects where id=?',(source_id,)).fetchone()[0]);db.close()
    os.environ['AGENTLAB_DATA']=str(root/'data/coverage-verification/real-isolated')
    from backend import generation as g,storage as s,agent,generation_flow as flow,generation_budget as b
    from backend.generation_schema import Request
    from backend.generation_coverage import CoverageError,summary,begin_or_continue
    assert agent.mode()=='real','Real model configuration unavailable'
    s.init();j=g.create(Request.model_validate(source['request']),direct_build=True,handoff=True,fault_model=True)
    for key in ('contract','contract_version','contract_hash','confirmed_version','confirmation','private_fault_requirements','assets','spec_approval','spec_reviews','installed_bundle','assessment','rationale','evaluation_candidate'):
        if key in source:j[key]=copy.deepcopy(source[key])
    refs=set(j['assets'].values())|{j['evaluation_candidate']['asset']}
    for ref in refs:shutil.copytree(root/'data/generation'/source_id/ref,g.root(j)/ref)
    j['budget']=b.initialize(b.BudgetPolicy(requests=8,output_tokens=40000,seconds=600,validations=3))
    j['source_replay']=source_id;g.put(j)
    raw=json.loads((g.root(j)/j['evaluation_candidate']['asset']/'rejected.json').read_text())
    exc=CoverageError(summary(j,raw));flow.failure(j,'evaluation',exc);begin_or_continue(j,exc)
    print(json.dumps({'id':j['id'],'source':source_id,'budget':j['budget']['policy']}),flush=True)
    g.launch(j['id'],'evaluation')
    while j['id'] in g.ACTIVE:time.sleep(1)
    j=g.get(j['id'])
    result={k:j.get(k) for k in ('id','status','error','request_count','coverage_repairs','budget')}
    result['gates']=(j.get('matrix') or {}).get('gates');result['matrix_id']=(j.get('matrix') or {}).get('id')
    result['attempts']=[{k:a.get(k) for k in ('stage','status','blind','error','metadata')} for a in j['attempts']]
    (s.DATA.parent/(j['id']+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:result[k] for k in ('id','status','error','request_count','gates','matrix_id')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
