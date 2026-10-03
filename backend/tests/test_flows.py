from sqlalchemy import select
from app.db import Session, Claim, Document, Finding
from app.engine import assess, evidence, analyse
from app.main import TOKENS

def prepare(client,auth):
    assert client.post('/api/demo/reset',headers=auth).status_code==200
    for action in ['generate','simulate_send']:
        assert client.post('/api/resolutions/RT-CG021/request',headers=auth,json={'action':action}).status_code==200
    return client.post('/api/resolutions/RT-CG021/simulate-response',headers=auth).json()['data']['response']

def test_seed_and_ground_truth(client,auth):
    claims=client.get('/api/claims',headers=auth).json()
    assert len(claims)==50
    assert all(c['status']==c['data']['ground_truth']['expected_state'] for c in claims)
    assert sum(c['status']=='READY' for c in claims)==20
    assert client.get('/api/claims/CG001',headers=auth).json()['readiness']==98
    assert client.get('/api/claims/CG048',headers=auth).json()['status']=='INVESTIGATION'

def test_resolution_real_api_and_targeted_runs(client,auth):
    prepare(client,auth)
    before=client.get('/api/claims/CG021',headers=auth).json()
    assert before['readiness']==63
    assert before['status']=='NEEDS_RESOLUTION'
    result=client.post('/api/resolutions/RT-CG021/complete',headers=auth).json()
    assert (result['readiness'],result['status'])==(94,'READY')
    assert result['tasks'][0]['status']=='COMPLETED'
    assert all(f['status']=='RESOLVED' for f in result['findings'])
    assert {r['agent'] for r in result['runs'][len(before['runs']):]}=={'Reading documents','Checking evidence','Checking clinical consistency','Preparing Claim Passport'}
    again=client.post('/api/resolutions/RT-CG021/complete',headers=auth).json()
    assert len(again['documents'])==len(result['documents'])
    assert len(again['runs'])==len(result['runs'])
    events=client.get('/api/audit?claim_id=CG021',headers=auth).json()
    assert {'DOCUMENT_VALIDATED','RESOLUTION_COMPLETED','PASSPORT_UPDATED','REQUEST_GENERATED','REQUEST_SIMULATED','RESPONSE_RECEIVED'} <= {e['event'] for e in events}
    assert client.post('/api/demo/reset',headers=auth).json()['readiness']==63

def test_invalid_response_cannot_raise_readiness(client,auth):
    valid=prepare(client,auth)
    wrong=valid.replace('Beneficiary 021','Beneficiary 999')
    client.post('/api/resolutions/RT-CG021/response',headers=auth,json={'text':wrong})
    assert client.post('/api/resolutions/RT-CG021/complete',headers=auth).status_code==422
    c=client.get('/api/claims/CG021',headers=auth).json()
    assert c['readiness']==63 and c['status']=='NEEDS_RESOLUTION'
    assert any(e['event']=='VALIDATION_FAILED' for e in client.get('/api/audit?claim_id=CG021',headers=auth).json())

def test_conflicting_duplicate_identity_rejected(client,auth):
    valid=prepare(client,auth)
    client.post('/api/resolutions/RT-CG021/response',headers=auth,json={'text':valid+'\nBeneficiary: Beneficiary 999'})
    assert client.post('/api/resolutions/RT-CG021/complete',headers=auth).status_code==422

def test_permissions_and_org_isolation(client,auth):
    assert client.get('/api/claims').status_code==401
    token=client.post('/api/session',json={'role':'Auditor'}).json()['token']; h={'Authorization':'Bearer '+token}
    assert client.get('/api/claims',headers=h).status_code==200
    assert client.post('/api/demo/reset',headers=h).status_code==403
    assert client.post('/api/resolutions/RT-CG021/complete',headers=h).status_code==403
    TOKENS['other-org']={'role':'Claims Executive','org_id':'other','id':'other'}
    assert client.get('/api/claims',headers={'Authorization':'Bearer other-org'}).json()==[]
    assert client.get('/api/claims/CG001',headers={'Authorization':'Bearer other-org'}).status_code==404
    assert client.post('/api/findings/CG030-F04/decision',headers=auth,json={'decision':'INCORRECT','reason':'Reviewed'}).status_code==403

def test_human_decision_preserves_original(client,auth):
    token=client.post('/api/session',json={'role':'Medical Reviewer'}).json()['token'];h={'Authorization':'Bearer '+token}
    assert client.post('/api/findings/CG030-F04/decision',headers=h,json={'decision':'INCORRECT','reason':''}).status_code==422
    assert client.post('/api/findings/CG030-F04/decision',headers=h,json={'decision':'INCORRECT','reason':'Requires corrected package interpretation'}).status_code==200
    c=client.get('/api/claims/CG030',headers=h).json()
    assert c['findings'][0]['status']=='OPEN'
    assert c['decisions'][0]['data']['reason']=='Requires corrected package interpretation'

def test_billing_citation(client,auth):
    c=client.get('/api/claims/CG030',headers=auth).json()
    f=next(f for f in c['findings'] if f['rule']=='F04')
    citation=f['data']['evidence'][0]
    assert 'anaesthesia' in citation['text']
    assert {'source','page','section','version','id','effective_date','authority','timestamp'}<=citation.keys()

def test_hard_gates_and_chronology(client):
    with Session() as s:
        c=s.get(Claim,'CG001');docs=s.scalars(select(Document).where(Document.claim_id==c.id)).all()
        c.data={**c.data,'policy_active':False}
        score,state,_,_=assess(c,docs)
        assert score<=49 and state=='HUMAN_REVIEW'
        c.data={**c.data,'policy_active':True,'identity_conflict':True}
        assert assess(c,docs)[0]<=39
        c.data={**c.data,'identity_conflict':False,'discharge':'2026-09-01'}
        assert any(x[0]=='F11' for x in assess(c,docs)[3])

def test_effective_date_filter(client):
    with Session() as s:
        assert evidence(s,'DOC-4.2','2025-12-31') is None
        assert evidence(s,'DOC-4.2','2026-10-02')['page']==4

def test_hash_reuse_and_export(client,auth):
    with Session() as s:
        docs=s.scalars(select(Document).where(Document.claim_id.in_([f'CG{i:03}' for i in range(45,51)]),Document.kind=='diagnostic_report')).all()
        assert len(docs)==6 and len({d.hash for d in docs})==1
    c=client.get('/api/claims/CG001/passport',headers=auth).json()
    assert c['readiness']==98 and c['documents']
    assert any(e['event']=='PASSPORT_EXPORTED' for e in client.get('/api/audit?claim_id=CG001',headers=auth).json())

def test_illegal_task_transition(client,auth):
    client.post('/api/demo/reset',headers=auth)
    assert client.post('/api/resolutions/RT-CG021/complete',headers=auth).status_code==409
    assert client.post('/api/resolutions/RT-CG021/request',headers=auth,json={'action':'simulate_send'}).status_code==409

def test_policy_service_failure_is_not_pass(client):
    with Session() as s:
        c=s.get(Claim,'CG001');c.data={**c.data,'admission':'2027-01-01','discharge':'2027-01-03'}
        analyse(s,c)
        assert c.status=='HUMAN_REVIEW' and c.data['checks']['policy']==0 and c.readiness<=49

def test_integrity_is_calculated_from_documents(client):
    with Session() as s:
        c=s.get(Claim,'CG048')
        assert c.data['network_observed']['reused_claims']==[f'CG{i:03}' for i in range(45,51)]
        d=s.scalar(select(Document).where(Document.claim_id==c.id,Document.kind=='diagnostic_report'))
        d.hash='unique-test-hash';s.flush();analyse(s,c)
        assert c.status=='READY' and not c.data['network_observed']['reused_claims']
