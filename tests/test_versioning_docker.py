"""Task modules are copied as bytes, and executed exclusively by Docker."""
import json
import shutil
import pytest
from backend import executor, storage as s

pytestmark=pytest.mark.skipif(not executor.availability()[0],reason='Docker unavailable: never execute task modules on host')
PACKAGE=s.TASKS/'rag_versioning/1.0.0'
FILES=json.loads((PACKAGE/'manifest.json').read_text())['readable']
CASES=json.loads((PACKAGE/'public_cases.json').read_text())+json.loads((PACKAGE/'private/hidden_cases.json').read_text())


def install(folder,variant):
    folder.chmod(0o755)
    source=PACKAGE/('initial' if variant=='initial' else 'private/'+variant)
    for name in FILES:shutil.copyfile(source/name,folder/name)


def execute(folder,case):
    value=executor.execute(folder,case['input'],allowed_files=FILES)
    assert isinstance(value,dict) and 'result' in value and 'error' not in value, '加载/运行错误不能计为故障复现'
    return value


@pytest.mark.parametrize('variant',['initial','normal','reference'])
def test_versioning_versions(tmp_path,variant,record_property):
    install(tmp_path,variant)
    observed=[]
    for case in CASES:
        actual=execute(tmp_path,case)
        observed.append({'id':case['id'],'passed':actual['result']==case['expected'],'actual':actual['result']})
    record_property('matrix',json.dumps(observed,ensure_ascii=False))
    if variant=='initial':
        assert all(o['passed'] for o,c in zip(observed,CASES) if c['group']=='regression')
        target=next(c for c in CASES if c['id']=='version-update')
        for _ in range(2):
            actual=execute(tmp_path,target)
            assert actual['result']['queries'][0]['citations'][0]['version']==1
            assert actual['result']['queries'][0]['answer']=='退款 政策 旧规则 7天'
            assert target['expected']['queries'][0]['citations'][0]['version']==2
            assert actual['trace'][2]['chunks_after']==3
    else:assert all(o['passed'] for o in observed)


@pytest.mark.parametrize('evasion',['clear_all','unconditional','rank_only','memory_only'])
def test_versioning_evasions(tmp_path,evasion,record_property):
    install(tmp_path,'initial' if evasion=='rank_only' else 'reference')
    path=tmp_path/'index_store.py';code=path.read_text()
    if evasion=='clear_all':
        code=code.replace("DELETE FROM chunks WHERE document_id=?', (document_id,)", "DELETE FROM chunks', ()")
    elif evasion=='unconditional':
        code=code.replace("        if row is not None and version <= row['version']:\n            return\n",'')
    elif evasion=='rank_only':
        r=tmp_path/'retrieval.py';r.write_text(r.read_text().replace("item['version']", "-item['version']"))
    else:
        code=code.replace('self.db = sqlite3.connect(path)','self.volatile = {}\n        self.db = sqlite3.connect(path)')
        code=code.replace('        with self.db:',"        if row is not None:\n            self.volatile[document_id] = chunks\n            return\n        with self.db:")
        code=code.replace("return [dict(row) for row in self.db.execute('SELECT * FROM chunks ORDER BY document_id, version, position')]", "return [dict(row) for row in self.db.execute('SELECT * FROM chunks ORDER BY document_id, version, position') if row['document_id'] not in self.volatile] + [c for chunks in self.volatile.values() for c in chunks]")
    path.write_text(code)
    normal=next(c for c in CASES if c['id']=='version-repeat')
    assert execute(tmp_path,normal)['result']==normal['expected']
    target_id={'clear_all':'version-isolation','unconditional':'version-delayed','rank_only':'version-old-keyword','memory_only':'version-reopen'}[evasion]
    target=next(c for c in CASES if c['id']==target_id)
    actual=execute(tmp_path,target)
    assert actual['result']!=target['expected']
    record_property('evasion_evidence',json.dumps({'case':target_id,'actual':actual['result'],'expected':target['expected']},ensure_ascii=False))


def test_multifile_submission_docker(client):
    import time
    from backend import storage as s, workspace as w, agent
    session=client.post('/api/sessions',json={'task_id':'rag_versioning'}).json()
    url='/api/sessions/'+session['id']
    codes={name:(PACKAGE/'private/reference'/name).read_text() for name in w.permissions(session)['editable']}
    assert client.put(url+'/files',json={'files':codes,'diagnosis':'替换同文档旧片段，保留版本门槛与其他文档。'}).status_code==200
    client.post(url+'/hint')
    submission=client.post(url+'/submit').json()
    # Change another module immediately after submit; reports use the captured snapshot.
    codes['context_builder.py']+='\n# later revision\n'
    client.put(url+'/files',json={'files':codes,'diagnosis':'later'})
    client.post(url+'/hint')
    deadline=time.monotonic()+110
    while time.monotonic()<deadline:
        state=client.get(url).json()
        if state['reports'] and state['reports'][0]['feedback_status']!='generating':break
        time.sleep(.2)
    report=state['reports'][0]
    assert report['objective']['status']=='passed'
    assert len(report['objective']['checks'])==15
    assert report['snapshot']==submission['snapshot']==report['objective']['snapshot']
    assert len(report['objective']['hints'])==1 and report['diagnosis']!='later'
    contents=client.get(url+'/snapshots/'+report['snapshot']).json()['files']
    assert len(contents)==6 and '# later revision' not in contents['context_builder.py']
    assert report['snapshot']!=w.snapshot(s.get('session',session['id']))
    public=[c for c in report['objective']['checks'] if c.get('diagnostic_trace')]
    assert len(public)==3 and all(c['visibility']=='public' for c in public)
    assert all('diagnostic_trace' not in c for c in report['objective']['checks'] if c['visibility']=='hidden')
    observed=agent.tool(session,'get_run_result',{'run_id':submission['id']})
    assert any(c.get('diagnostic_trace') for c in observed['checks'])
    assert client.get('/api/reports/'+report['id']).json()==report
