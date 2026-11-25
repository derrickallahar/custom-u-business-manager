import copy,json,unittest
from pathlib import Path
from production_app import create_app,Failure
from hr_rules import check_record,validate_hr,shift_totals,lieu_balances
ORIGIN='https://clock.example.invalid';ID='12900000-0000-4000-8000-000000000001'
class Provider:
    allowed=True
    def __init__(self):self.calls=[]
    def login(self,*a):return {'access_token':'fixture-token','expires_in':3600}
    def access(self,*a):
        if not self.allowed:raise Failure('ACCESS_DENIED',403)
        return {'user_id':ID,'email':'fixture@example.invalid','role':'admin'}
    def call(self,path,token,body,limit=0):
        self.calls.append(body)
        return json.dumps({'user_id':ID,'now':'2026-11-25T15:00:00Z','shift':None}).encode()
class Clock(unittest.TestCase):
    def test_zero_correction_and_backup_replay(self):
        obj=json.loads(Path('/tmp/clock129_records.json').read_text());validate_hr(obj)
        zeros=[r for r in obj['hr_records'] if r['kind']=='shift' and r['data'].get('correction') and r['data']['correction']['in']==r['data']['correction']['out']]
        self.assertEqual(len(zeros),2)
        for r in zeros:
            totals=shift_totals(r['data'],r['updated_at']);self.assertEqual(totals['worked_minutes'],0);self.assertEqual(totals['overtime_minutes'],0);self.assertFalse(totals['needs_review']);self.assertIsNone(r['data']['intervals'][0]['out'])
        self.assertTrue(all(b['approved_minutes']==0 for b in lieu_balances(obj['hr_records'])))
        bad=copy.deepcopy(obj);next(r for r in bad['hr_records'] if r['id']==zeros[0]['id'])['data']['correction']['out']='2020-01-01T00:00:00Z'
        with self.assertRaises(ValueError):validate_hr(bad)
    def test_authenticated_own_clock_and_shared_pages(self):
        p=Provider();app=create_app(p,ORIGIN,'',True,enforce_devices=False);client=app.test_client()
        get=lambda path:client.get(path,base_url=ORIGIN)
        self.assertEqual(get('/api/hr/clock').status_code,401)
        for path in ['/','/quotes/new','/invoices/new','/mockups/new','/products','/hr','/hr/training','/account']:
            r=get(path);self.assertEqual(r.status_code,200);self.assertIn(b'workspace-clock.js?v=129',r.data)
        self.assertEqual(get('/workspace-assets/workspace-clock.js').status_code,200)
        self.assertEqual(client.post('/api/login',json={'email':'fixture@example.invalid','password':'fixture-password'},headers={'Origin':ORIGIN},base_url=ORIGIN).status_code,200)
        result=get('/api/hr/clock');self.assertEqual(result.status_code,200);self.assertEqual(p.calls[-1],{'payload':{'op':'clock_view'}});self.assertEqual(result.headers['Cache-Control'],'no-store');self.assertEqual(set(result.json),{'user_id','now','shift'})
        self.assertEqual(client.post('/api/hr/action',json={'op':'clock_in'},headers={'Origin':'https://wrong.invalid'},base_url=ORIGIN).status_code,403)
        self.assertEqual(client.post('/api/hr/action',json={'op':'clock_view'},headers={'Origin':ORIGIN},base_url=ORIGIN).status_code,400)
        p.allowed=False;self.assertEqual(get('/api/hr/clock').status_code,403)
if __name__=='__main__':unittest.main()
