import os, sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vendor'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['DATABASE_URL']=os.getenv('CLAIMGUARD_TEST_DATABASE_URL') or 'sqlite:///'+str(Path(tempfile.mkdtemp())/'test.db')
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope='session')
def client():
    with TestClient(app) as c: yield c

@pytest.fixture
def auth(client):
    token=client.post('/api/session',json={'role':'Claims Executive'}).json()['token']
    return {'Authorization':'Bearer '+token}
