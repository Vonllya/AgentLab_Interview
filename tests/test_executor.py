import subprocess
import sys
import pytest
from backend import executor


def test_timeout_cleanup(tmp_path,monkeypatch):
    (tmp_path/'solution.py').write_text('# never executed on host')
    actual=subprocess.Popen
    def spawn(*args,**kwargs):
        # Trusted fixture only, exercises transport deadline without Docker.
        return actual([sys.executable,'-c','import time; time.sleep(2)'],**kwargs)
    cleanup=[]
    monkeypatch.setattr(executor.subprocess,'Popen',spawn)
    monkeypatch.setattr(executor.subprocess,'run',lambda cmd,**kwargs:cleanup.append(cmd))
    with pytest.raises(TimeoutError):executor.execute(tmp_path,{},timeout=.1)
    assert cleanup and cleanup[0][:3]==['docker','rm','-f']


def test_output_limit(tmp_path,monkeypatch):
    (tmp_path/'solution.py').write_text('# never executed on host')
    actual=subprocess.Popen
    monkeypatch.setattr(executor.subprocess,'Popen',lambda *a,**kw:actual([sys.executable,'-c','print("x"*40000)'],**kw))
    monkeypatch.setattr(executor.subprocess,'run',lambda *a,**kw:None)
    with pytest.raises(ValueError,match='32 KiB'):executor.execute(tmp_path,{})
