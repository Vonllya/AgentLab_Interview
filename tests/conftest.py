import pytest
from fastapi.testclient import TestClient
from backend import storage as s
from backend.app import app

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(s,'DATA',tmp_path/'data')
    monkeypatch.setenv('AGENT_MODE','mock')
    with TestClient(app) as client:
        yield client

@pytest.fixture
def session(client):
    return client.post('/api/sessions',json={'task_id':'rag'}).json()
