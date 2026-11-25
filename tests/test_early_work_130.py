import copy,csv,io,json,unittest
from pathlib import Path
from production_app import create_app,Failure
from hr_rules import validate_hr,shift_totals
from training_rules import validate_course
from pypdf import PdfReader
ORIGIN='https://attendance.example.invalid';fixture=json.loads(Path('/tmp/early130_cases.json').read_text())
class Provider:
    def login(self,*a):return {'access_token':'fixture-token','expires_in':3600}
    def access(self,*a):return {'user_id':fixture['view']['user_id'],'email':'admin@example.invalid','role':'admin'}
    def call(self,path,token,body,limit=0):
        if body['payload']['op']=='view':return json.dumps(self.view).encode()
        self.payload=body['payload'];return json.dumps({'data':self.view['records'][0]}).encode()
class EarlyWork(unittest.TestCase):
    def test_python_matches_database_and_backup_replays(self):
        validate_hr(fixture['backup'])
        for c in fixture['cases']:
            self.assertEqual(shift_totals(c['row']['data'],c['row']['updated_at']),c['totals'],c['name'])
        bad=copy.deepcopy(fixture['backup']);r=next(r for r in bad['hr_records'] if r['data'].get('early_report',{}).get('kind')=='work');r['data']['early_report']['intervals'][0]['out']=r['data']['early_report']['intervals'][0]['in']
        with self.assertRaises(ValueError):validate_hr(bad)
    def test_actual_csv_handoff_all_four_cases_and_pending(self):
        p=Provider();p.view={**fixture['view'],'records':[c['row'] for c in fixture['cases']]};app=create_app(p,ORIGIN,'',True,enforce_devices=False);client=app.test_client()
        client.post('/api/login',json={'email':'admin@example.invalid','password':'fixture-password'},headers={'Origin':ORIGIN},base_url=ORIGIN)
        r=client.get('/api/hr/timesheet.csv?from=2026-11-30&to=2026-12-03',base_url=ORIGIN);self.assertEqual(r.status_code,200)
        rows=list(csv.DictReader(io.StringIO(r.data.decode('utf-8-sig'))));self.assertEqual(len(rows),5)
        expected={'2026-11-30':[480],'2026-12-01':[480,510],'2026-12-02':[510],'2026-12-03':[0]}
        for day,values in expected.items():self.assertEqual([int(x['Counted work minutes']) for x in rows if x['Date']==day],values)
        pending=next(x for x in rows if x['Manager review status']=='pending');self.assertEqual(pending['Reported early work minutes'],'30');self.assertEqual(pending['Unresolved early minutes (not yet classified as work)'],'30');self.assertIn('Unresolved',pending['Payroll handoff status'])
        self.assertNotIn('Overtime minutes',rows[0]);self.assertFalse(any('lieu' in k.lower() or 'credit' in k.lower() for k in rows[0]))
        corrected=next(x for x in rows if x['Date']=='2026-12-02');self.assertEqual(json.loads(corrected['Original punches'])[0]['in'],'2026-12-02T14:15:00+00:00');self.assertEqual(json.loads(corrected['Separate correction'])['in'],'2026-12-02T13:30:00+00:00')
        # The separate bank export never implies a payroll amount or subtracts work minutes.
        r=client.get('/api/hr/time-off-credits.csv?from=2026-11-30&to=2026-12-03',base_url=ORIGIN);self.assertEqual(r.status_code,200);self.assertNotIn('Counted work minutes',r.data.decode('utf-8-sig'))
        p.view['records']=[fixture['cases'][0]['row']]
        r=client.post('/api/hr/action',json={'op':'early_work_report','id':p.view['records'][0]['id'],'version':1,'kind':'work','intervals':[{'in':'2026-11-30T08:30','out':'2026-11-30T09:00'}],'note':'Actual work'},headers={'Origin':ORIGIN},base_url=ORIGIN)
        self.assertEqual(r.status_code,200);self.assertEqual(p.payload['intervals'][0]['in'],'2026-11-30T08:30:00-05:00')
    def test_guide_pdf_and_question_16(self):
        current=json.loads(Path('production_history/training_starter_130.json').read_text());old=json.loads(Path('production_history/training_starter_128.json').read_text());validate_course(current)
        self.assertEqual(current['edition'],'3');self.assertEqual(current['lessons'][7]['body'].split('Requesting time off')[1],old['lessons'][7]['body'].split('Requesting time off')[1])
        for i in range(20):
            if i!=15:self.assertEqual(current['questions'][i],old['questions'][i])
        q=current['questions'][15];self.assertIn('Report the actual early work',q['options'][q['correct_index']]);self.assertIn('prior early-start approval',q['prompt'])
        pdf=PdfReader('output/pdf/CustomU_Business_Manager_Training_Guide.pdf');text=' '.join(' '.join(p.extract_text() for p in pdf.pages).split())
        for s in ['Edition 3','24 hours before it starts','14 calendar days','does not make actual work disappear','do not replace legally required overtime pay','16. An employee actually works']:self.assertIn(s,text)
        self.assertNotIn('Unapproved time before the scheduled',text)
        for p in pdf.pages:self.assertTrue(p.images)
if __name__=='__main__':unittest.main()
