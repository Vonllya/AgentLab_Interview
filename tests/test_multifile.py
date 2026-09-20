"""Permissions and storage tests do not execute or import task business code."""
import hashlib
import json
import pytest
from backend import workspace as w, storage as s, agent, evidence


def advanced(client):
    response=client.post('/api/sessions',json={'task_id':'rag_versioning'})
    assert response.status_code==200
    return response.json()


def test_manifest_access_shared_by_api_and_tools(client):
    session=advanced(client); url='/api/sessions/'+session['id']
    state=client.get(url).json()
    assert len(state['files'])==6 and len(state['permissions']['editable'])==5
    assert agent.tool(session,'list_workspace_files',{})==state['permissions']['readable']
    for name,code in state['files'].items():
        assert client.get(url+'/files',params={'path':name}).json()['content']==code
        assert agent.tool(session,'read_workspace_file',{'path':name})==code
    for name in ['private/reference/index_store.py','/etc/passwd','../index_store.py','x/../index_store.py','public_test.py','manifest.json','.env','unknown.py']:
        assert client.get(url+'/files',params={'path':name}).status_code==400
        with pytest.raises(ValueError): agent.tool(session,'read_workspace_file',{'path':name})
    assert 'private_assets' not in client.get('/api/tasks').text
    assert 'private' not in json.dumps(agent.tool(session,'get_task_brief',{}))


def test_save_all_validation_atomicity_and_isolation(client):
    session=advanced(client); other=advanced(client); original=w.read_all(session)
    edits={name:original[name]+'\n# edit\n' for name in w.permissions(session)['editable']}
    url='/api/sessions/'+session['id']+'/files'
    for bad in [dict(edits,**{'solution.py':'bad'}),{'index_store.py':'incomplete'},dict(edits,**{'pipeline.py':'x'*65537})]:
        assert client.put(url,json={'files':bad}).status_code==400
        assert w.read_all(s.get('session',session['id']))==original
    assert client.put(url,json={'files':edits,'diagnosis':'saved'}).status_code==200
    current=s.get('session',session['id'])
    assert current['workspace']!=session['workspace']
    assert w.read_all(current)=={**original,**edits}
    assert w.read_all(other)==original
    # A stale Agent session must follow the current revision pointer.
    assert agent.tool(session,'read_workspace_file',{'path':'pipeline.py'})==edits['pipeline.py']
    assert w.read_all(current)['solution.py']==original['solution.py']


def test_symlink_boundaries(client,tmp_path):
    session=advanced(client)
    path=w.safe_file(session,'index_store.py'); path.unlink();path.symlink_to('/etc/passwd')
    with pytest.raises(ValueError):w.read_all(session)
    with pytest.raises(ValueError):w.snapshot(session)
    other=advanced(client); base=s.DATA/other['workspace']; relocated=tmp_path/'relocated';base.rename(relocated);base.symlink_to(relocated,target_is_directory=True)
    with pytest.raises(ValueError):w.safe_file(other,'pipeline.py')


def test_multifile_snapshot_stability_and_report_immutability(client):
    session=advanced(client); original=w.read_all(session); first=w.snapshot(session)
    editable=w.permissions(session)['editable']
    w.save_files(session,{name:original[name] for name in reversed(editable)},'original diagnosis')
    assert w.snapshot(session)==first
    for name in editable:
        codes={key:original[key] for key in editable};codes[name]+='\n# distinct\n'
        w.save_files(session,codes,'submitted diagnosis'); digest=w.snapshot(session)
        assert digest!=first and w.snapshot_contents(session,digest)[name]==codes[name]
    report={'run_id':'a'*32,'snapshot':digest,'diagnosis':'submitted diagnosis','objective':{'checks':[],'hints':[{'id':'h','level':1}]}}
    messages=agent.report_messages(session,report)
    w.save_files(session,{name:original[name]+'\n# future\n' for name in editable},'future diagnosis')
    agent.hint(session);agent.hint(session)
    assert agent.report_messages(session,report)==messages
    assert 'future' not in json.dumps(messages)
    assert w.snapshot_contents(session,first)==original
    assert name in w.diff(session,digest)


def test_legacy_snapshot_digest_and_interface(client,session):
    code=w.read(session)
    assert w.snapshot(session)==hashlib.sha256((session['task_id']+'@'+session['version']+'\0'+code).encode()).hexdigest()
    assert client.put('/api/sessions/'+session['id']+'/files',json={'code':code+'\n# legacy'}).status_code==200
    assert w.read(session).endswith('# legacy')


def test_public_trace_is_untrusted_hidden_trace_never_exposed(client):
    session=advanced(client)
    run={'checks':[{'id':'version-update','visibility':'public','status':'failed','diagnostic_trace':{'source':'user_code','events':['trace']},'detail':'old rule'},
                   {'id':'opaque','visibility':'hidden','status':'passed','diagnostic_trace':{'secret':'SECRET'},'detail':'SECRET'},
                   {'id':'modification-scope','status':'passed','visibility':'public'}]}
    result=evidence.run_evidence(session,run)
    assert result['checks'][0]['diagnostic_trace']['source']=='user_code'
    assert '非通过证明' in result['checks'][0]['coverage']['not_proven']
    assert 'SECRET' not in json.dumps(result)
    assert result['checks'][2]['category']=='modification_scope'
    assert '不是独立可信' in agent.SYSTEM


def test_readonly_snapshot_asset_tamper_rejected(client):
    session=advanced(client);digest=w.snapshot(session)
    path=s.DATA/'snapshots'/digest/'solution.py';path.chmod(0o644);path.write_text('# changed')
    with pytest.raises(ValueError,match='只读'):w.snapshot_contents(session,digest)
