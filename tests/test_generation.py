import json
import time
import pytest
from backend import generation as g, storage as s, workspace as w, agent
from backend.generation_schema import Contract,Design,Project,Evaluation,Request,validate_project,validate_evaluation
from backend.generation_mock import response


def ready_job():
    job=g.create(Request(requirement='本地工具超时重试的副作用训练'),policy=False)
    design=response('design',{})
    job.update(contract=design['contract'],private_fault_requirements='PRIVATE-FAULT',contract_version=1,contract_hash=g.digest(design['contract']),assessment='simulation',status='awaiting_contract')
    g.put(job);return job


def test_context_isolation(client):
    job=ready_job()
    build=g.model_stage(job,'build')
    evaluator=g.context(job,'evaluation')
    serialized=json.dumps(evaluator)
    assert 'PRIVATE-FAULT' not in serialized and 'fault_explanation' not in serialized
    assert 'normal' not in evaluator and 'reference' not in evaluator
    assert evaluator['contract_hash']==job['contract_hash']
    assert g.context(job,'build')['private_fault_requirements']=='PRIVATE-FAULT'
    assert 'messages' not in evaluator


@pytest.mark.parametrize('files',[['app.py','../x.py'],['app.py','/tmp/x.py'],['app.py','solution.py'],['app.py','app.py'],['app.py','os.py']])
def test_contract_paths(client,files):
    contract=response('design',{})['contract'];contract['files']=files
    with pytest.raises(ValueError):Contract.model_validate(contract)


def test_assets_schema_and_limits(client):
    contract=Contract.model_validate(response('design',{})['contract'])
    project=Project.model_validate(response('build',{}));validate_project(project,contract)
    project.faulty['app.py']='def invalid('
    with pytest.raises(SyntaxError):validate_project(project,contract)
    project=Project.model_validate(response('build',{}));project.normal['app.py']='x'*25000
    with pytest.raises(ValueError):validate_project(project,contract)
    ev=Evaluation.model_validate(response('evaluation',{}));validate_evaluation(ev,contract)
    ev.cases[0].expected='wrong-type'
    with pytest.raises(ValueError):validate_evaluation(ev,contract)
    ev=Evaluation.model_validate(response('evaluation',{}));ev.cases[0].covers=['secret_requirement']
    with pytest.raises(ValueError):validate_evaluation(ev,contract)


def test_confirmation_revision_retry_and_budget(client,monkeypatch):
    job=ready_job()
    with pytest.raises(ValueError):g.confirm(job['id'],1,False)
    with pytest.raises(ValueError):g.confirm(job['id'],99,True)
    revised=g.revise(job['id'],Contract.model_validate(job['contract']))
    assert revised['contract_version']==2 and revised['confirmed_version'] is None
    current=g.get(job['id']);current.update(status='failed',stage='build',request_count=10);g.put(current)
    with pytest.raises(ValueError,match='预算'):g.retry(job['id'])
    current.update(request_count=3,attempts=[{'stage':'build','contract_version':2}]*3);g.put(current)
    with pytest.raises(ValueError,match='预算'):g.retry(job['id'])


def test_cancel_late_result_and_restart(client):
    job=ready_job();g.cancel(job['id']);job['status']='building';g.put(job)
    assert g.get(job['id'])['status']=='cancelled'
    with pytest.raises(InterruptedError):g.model_stage(job,'build')
    another=ready_job();another['status']='building';another['stage']='build';g.put(another)
    g.recover();assert g.get(another['id'])['status']=='interrupted'
    assert g.get(another['id'])['request_count']==0


def test_cannot_publish_unverified_or_leak_to_training(client):
    job=ready_job()
    with pytest.raises(ValueError):g.publish(job['id'],True,'已检查契约与行为的一致性','0'*64)
    assert not any(t['id'].startswith('gen_') for t in client.get('/api/tasks').json())
    assert client.post('/api/sessions',json={'task_id':'gen_'+job['id']}).status_code==404
    sess=w.create('rag')
    with pytest.raises(ValueError):agent.tool(sess,'read_workspace_file',{'path':'generation.py'})
    assert 'private_fault_requirements' not in g.public(job)


def wait(id,terminal,timeout=120):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        job=g.get(id)
        if job['status'] in terminal:return job
        time.sleep(.05)
    raise AssertionError('generation stuck: '+g.get(id)['status'])


def test_generated_docker_publish_train_freeze(client):
    if not g.executor.availability()[0]:pytest.skip('Docker unavailable; no host fallback')
    job=g.create(Request(requirement='MOCK 离线验证平台流程，不代表真实生成'))
    g.analyze(job['id']);job=wait(job['id'],{'awaiting_contract','failed'})
    assert job['status']=='awaiting_contract'
    g.confirm(job['id'],job['contract_version'],True)
    job=wait(job['id'],{'awaiting_review','failed'})
    assert job['status']=='awaiting_review',job.get('error')
    assert job['matrix']['passed'] and len(job['matrix']['checks'])==20
    assert all(c['status']!='error' for c in job['matrix']['checks'])
    review=g.review_assets(job['id'])
    with pytest.raises(ValueError):g.publish(job['id'],False,'已核对所有期望值与输入行为',review['review_digest'])
    publication=g.publish(job['id'],True,'离线平台回归审核：核对四个数学期望、故障指纹与两种规避；不计真实生成。',review['review_digest'])
    assert g.publish(job['id'],True,'重复发布请求不重复创建任务',review['review_digest'])==publication
    assert publication['version']=='1.0.0'
    session=w.create(publication['task_id']);original=w.read_all(session)
    assert 'MOCK' in s.get('task',publication['task_id'])['title']
    with pytest.raises(ValueError):w.safe_file(session,'private/reference/app.py')
    ref=g.asset(job,'build')['reference'];w.save_files(session,ref,'检查负数和多元素，使用全部整数累加')
    snap=w.snapshot(session)
    response=client.post('/api/sessions/'+session['id']+'/submit');assert response.status_code==200
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        state=client.get('/api/sessions/'+session['id']).json()
        if state['reports'] and state['reports'][0]['feedback_status']!='generating':break
        time.sleep(.1)
    report=state['reports'][0]
    assert report['objective']['status']=='passed' and report['snapshot']==snap
    assert not any('faulty_expected' in c for c in json.loads((s.package(session)/'public_cases.json').read_text()))
    frozen=(s.package(session)/'initial/calculator.py').read_text()
    ref['calculator.py']+='\n# later'
    w.save_files(session,ref,'later');assert w.snapshot(session)!=snap
    assert (s.package(session)/'initial/calculator.py').read_text()==frozen
    with pytest.raises(ValueError):g.revise(job['id'],Contract.model_validate(job['contract']))
    s.init();assert s.get('task',publication['task_id'])['version']=='1.0.0'
    fork=g.fork(job['id']);changed=Contract.model_validate(fork['contract']);changed.title+=' 第二版'
    revised=g.revise(fork['id'],changed);g.confirm(fork['id'],revised['contract_version'],True)
    next_job=wait(fork['id'],{'awaiting_review','failed'})
    assert next_job['status']=='awaiting_review',next_job.get('error')
    second=g.publish(fork['id'],True,'再次核对新版本的全部契约、数据期望及执行证据。',next_job['review_digest'])
    assert second=={'task_id':publication['task_id'],'version':'1.0.1'}
    assert s.get('task',publication['task_id'])['title'].endswith('第二版')
    assert not agent.tool(session,'get_task_brief',{})['title'].endswith('第二版')
    assert s.package(session).name=='1.0.0'
    assert w.create(publication['task_id'])['version']=='1.0.1'


def test_generated_tests_are_data_not_python(client):
    obj=response('evaluation',{});obj['python']='import os; os.system("id")'
    with pytest.raises(ValueError):Evaluation.model_validate(obj)
    contract=Contract.model_validate(response('design',{})['contract'])
    project=Project.model_validate(response('build',{}));project.evasions['normal']=project.normal
    with pytest.raises(ValueError,match='冲突'):validate_project(project,contract)


def test_stage_repair_limit_and_audit(client):
    job=ready_job()
    for _ in range(3):g.model_stage(job,'build')
    with pytest.raises(ValueError,match='预算'):g.model_stage(job,'build')
    assert len(job['attempts'])==3
    for attempt in job['attempts']:
        messages=json.loads((g.root(job)/attempt['asset']/'input.json').read_text())
        assert g.digest(messages)==attempt['input_hash']
        assert attempt['metadata']['model'].startswith('MOCK')


def test_fault_error_never_counts_as_trigger(client,monkeypatch):
    # Transport fixture, not Docker proof. The same trusted gate must reject exceptions.
    job=ready_job();g.model_stage(job,'build');g.model_stage(job,'evaluation')
    monkeypatch.setattr(g.executor,'availability',lambda:(True,''))
    from types import SimpleNamespace
    monkeypatch.setattr(g.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout='test-image-id'))
    monkeypatch.setattr(g.executor,'execute',lambda *a,**k:{'error':'ImportError'})
    with pytest.raises(ValueError,match='门禁失败'):g.validate(job)
    assert not job['matrix']['gates']['fault_trigger']
    assert not job['matrix']['gates']['no_runtime_errors']
    assert all(c['status']=='error' for c in job['matrix']['checks'])
    previous=job['matrix']['id']
    with pytest.raises(ValueError,match='门禁失败'):g.validate(job)
    assert job['validation_history'][0]['id']==previous
    assert job['matrix']['id']!=previous


def test_public_generation_matrix_does_not_expose_private_results(client):
    job=ready_job();job['matrix']={'checks':[{'id':'x','visibility':'hidden','actual':'PRIVATE_ACTUAL','expected':'PRIVATE_EXPECTED','status':'failed'}]}
    encoded=json.dumps(g.public(job))
    assert 'PRIVATE_ACTUAL' not in encoded and 'PRIVATE_EXPECTED' not in encoded
    g.put(job)
    assert g.review_assets(job['id'])['matrix']['checks'][0]['expected']=='PRIVATE_EXPECTED'
    g.cancel(job['id'])
    with pytest.raises(ValueError):g.revise(job['id'],Contract.model_validate(job['contract']))


def test_resume_completed_model_checkpoint_without_repaying(client,monkeypatch):
    job=ready_job();g.model_stage(job,'build')
    calls=job['request_count'];job.update(status='interrupted',stage='build');g.put(job)
    launched=[]
    monkeypatch.setattr(g,'launch',lambda id,stage:launched.append(stage))
    g.retry(job['id']);assert launched==['evaluation']
    assert g.get(job['id'])['request_count']==calls
    g.model_stage(job,'evaluation');job.update(status='interrupted',stage='evaluation');g.put(job)
    g.retry(job['id']);assert launched[-1]=='validation'


def test_generated_runtime_image_is_server_pinned(tmp_path):
    from backend.executor import docker_command
    image='sha256:'+'1'*64
    cmd=docker_command(tmp_path,'test',image)
    assert cmd[-1]==image and cmd[cmd.index('--pull')+1]=='never'
    with pytest.raises(ValueError):docker_command(tmp_path,'test','attacker/image:latest')


def test_reanalysis_invalidates_assets_and_confirmation(client,monkeypatch):
    job=ready_job();g.model_stage(job,'build')
    job.update(status='failed',confirmed_version=1);g.put(job)
    launched=[];monkeypatch.setattr(g,'launch',lambda id,stage:launched.append(stage))
    g.reanalyze(job['id'],'一次输入包含整个操作序列，不依赖其他容器状态')
    updated=g.get(job['id'])
    assert launched==['design'] and not updated['assets']
    assert updated['confirmed_version'] is None
    assert updated['contract_history'][0]['assets']['build']
    assert updated['request_count']==job['request_count']


@pytest.mark.parametrize('field,value',[('required',[{}]),('enum',None),('additionalProperties',{'type':'string'})])
def test_malformed_schema_rejected_as_validation_error(client,field,value):
    raw=response('design',{})['contract'];raw['input_schema'][field]=value
    with pytest.raises(ValueError):Contract.model_validate(raw)


def test_evaluator_repair_is_explicit_audited_and_separate(client,monkeypatch):
    job=ready_job();g.model_stage(job,'build');g.model_stage(job,'evaluation')
    previous=job['assets']['evaluation'];build=job['assets']['build']
    job.update(status='failed',stage='validation');g.put(job)
    launched=[];monkeypatch.setattr(g,'launch',lambda id,stage:launched.append(stage))
    g.repair_evaluation(job['id'],'正常回归不能同时包含公开症状的故障触发条件。')
    updated=g.get(job['id'])
    assert launched==['evaluation'] and updated['assets']['build']==build
    assert updated['evaluation_history'][0]['asset']==previous
    assert 'evaluation' not in updated['assets']
    context=g.context(updated,'evaluation')
    assert 'previous_project' not in context and 'public_observations' not in context
    assert 'PRIVATE-FAULT' not in json.dumps(context)
    g.model_stage(updated,'evaluation')
    assert updated['attempts'][-1]['blind'] is False
    updated.update(status='failed',stage='validation',request_count=10);g.put(updated)
    with pytest.raises(ValueError,match='预算'):g.repair_evaluation(updated['id'],'不能绕过总请求预算再次调用。')
