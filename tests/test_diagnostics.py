import subprocess
from types import SimpleNamespace
import pytest
from backend import executor
from scripts.verify_acceptance import ORIGINAL_DOCKER_TESTS, REQUIRED_DOCKER_TESTS, verify_pytest, verify_browser

@pytest.mark.parametrize('stage,message,expected',[
    ('info','permission denied while trying to connect','permission_denied'),
    ('info','Cannot connect to the Docker daemon. Is the docker daemon running?','daemon_unreachable'),
    ('info','TLS certificate validation failed','daemon_error'),
    ('image','Error: No such image: agentlab-runner:0.1','image_missing'),
    ('image','permission denied','permission_denied'),
    ('image','unexpected response','image_error'),
])
def test_docker_reason_classes(monkeypatch,stage,message,expected):
    monkeypatch.setattr(executor.shutil,'which',lambda _: '/usr/bin/docker')
    def run(cmd,**kwargs):
        failed=cmd[1]==stage
        return SimpleNamespace(returncode=int(failed),stdout=b'',stderr=message.encode() if failed else b'')
    monkeypatch.setattr(executor.subprocess,'run',run)
    result=executor.diagnose()
    assert result['status']==expected
    assert result['cli']
    assert result['daemon']==(stage=='image')


def test_docker_missing_ready_timeout(monkeypatch):
    monkeypatch.setattr(executor.shutil,'which',lambda _:None)
    assert executor.diagnose()['status']=='cli_missing'
    monkeypatch.setattr(executor.shutil,'which',lambda _:'/usr/bin/docker')
    monkeypatch.setattr(executor.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=b'',stderr=b''))
    assert executor.diagnose()['status']=='ready'
    def timeout(*a,**k):raise subprocess.TimeoutExpired('docker',5)
    monkeypatch.setattr(executor.subprocess,'run',timeout)
    assert executor.diagnose()['status']=='check_timeout'


def test_acceptance_rejects_skipped_or_missing_docker_tests(tmp_path):
    import xml.etree.ElementTree as ET
    root=ET.Element('testsuite')
    for name in sorted(REQUIRED_DOCKER_TESTS):ET.SubElement(root,'testcase',classname='tests.test_docker_acceptance',name=name)
    path=tmp_path/'results.xml';ET.ElementTree(root).write(path)
    assert verify_pytest(path)['passed']
    ET.SubElement(root[0],'skipped');ET.ElementTree(root).write(path)
    result=verify_pytest(path);assert not result['passed'] and result['original_docker_passed']==12
    root.remove(root[0]);ET.ElementTree(root).write(path)
    assert not verify_pytest(path)['passed']
    original_only=ET.Element('testsuite')
    for name in sorted(ORIGINAL_DOCKER_TESTS):
        ET.SubElement(original_only,'testcase',classname='tests.test_docker_acceptance',name=name)
    ET.ElementTree(original_only).write(path)
    result=verify_pytest(path)
    assert result['original_docker_passed']==13 and result['docker_passed']==13
    assert not result['passed'], '新增的 5 项 Docker 验收也必须存在并通过'


def test_acceptance_rejects_skipped_browser_flow(tmp_path):
    import json
    path=tmp_path/'browser.json'
    path.write_text(json.dumps({'stats':{'expected':1,'skipped':1},'suites':[{'specs':[{'title':'真实 Docker 提交报告闭环','tests':[{'expectedStatus':'skipped','results':[{'status':'skipped'}]}]}]}]}))
    assert not verify_browser(path)['passed']
