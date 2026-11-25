import copy,io,json,unittest
from pathlib import Path
from pypdf import PdfReader
from production_app import create_app,Failure
from training_rules import validate_course,validate_training
from training_pdf import guide_pdf
ORIGIN='https://training.example.invalid'
COURSE=json.loads(Path('production_history/training_starter_127.json').read_text())
ID='12700000-0000-4000-8000-000000000050'
class Provider:
    def __init__(self):self.manager=True;self.allowed=True;self.calls=[]
    def login(self,email,password):return {'access_token':'fixture-token','expires_in':3600}
    def access(self,token):
        if not self.allowed:raise Failure('ACCESS_DENIED',403)
        return {'user_id':ID,'email':'fixture@example.invalid','role':'admin' if self.manager else 'production'}
    def logout(self,token):pass
    def call(self,path,token,body,limit=0):
        self.calls.append(body);p=body['payload'];op=p['op'];d=copy.deepcopy(COURSE)
        if not self.manager:
            for q in d['questions']:q.pop('correct_index');q.pop('explanation')
        if op=='list':r={'manager':self.manager,'courses':[],'people':[]}
        elif op=='get':r={'course':{'id':ID,'data':d}}
        elif op=='report':r={'course':{'title':'=unsafe','edition':'1'},'rows':[{'email':'+formula','active':True,'assigned':True,'due_date':None,'progress':None,'attempt_count':0}]} if self.manager else {'error':'ACCESS_DENIED'}
        else:r={'error':'ACCESS_DENIED'}
        return json.dumps(r).encode()
class Training(unittest.TestCase):
    def setUp(self):
        self.p=Provider();self.app=create_app(self.p,ORIGIN,'',True,enforce_devices=False);self.client=self.app.test_client()
    def get(self,path):return self.client.get(path,base_url=ORIGIN)
    def login(self):self.assertEqual(self.client.post('/api/login',json={'email':'fixture@example.invalid','password':'fixture-password'},base_url=ORIGIN,headers={'Origin':ORIGIN}).status_code,200)
    def test_routes_shell_and_no_public_answers(self):
        for path in ['/hr/training','/hr/training/new','/hr/training/'+ID,'/hr/training/'+ID+'/edit']:
            r=self.get(path);self.assertEqual(r.status_code,200);self.assertIn(b'workspace-shell.js',r.data);self.assertIn(b'training.js?v=127',r.data)
        self.assertIn(b'panel-training',self.get('/hr').data);self.assertEqual(self.get('/training.js').status_code,200)
        self.assertEqual(self.get('/training_starter_127.json').status_code,404)
        for path in ['/api/training?op=list','/api/training/'+ID+'/guide.pdf','/api/training/'+ID+'/answer-key.pdf','/api/training/'+ID+'/results.csv']:self.assertEqual(self.get(path).status_code,401)
    def test_guide_and_answer_key_permissions(self):
        self.p.manager=False;self.login();r=self.get('/api/training/'+ID+'/guide.pdf');self.assertEqual(r.status_code,200);self.assertEqual(r.headers['Cache-Control'],'no-store')
        text='\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(r.data)).pages);self.assertIn('Final knowledge test',text);self.assertNotIn('Training answer key',text)
        self.assertEqual(self.get('/api/training/'+ID+'/answer-key.pdf').status_code,403);self.assertEqual(self.get('/api/training/'+ID+'/results.csv').status_code,403)
        self.p.manager=True;r=self.get('/api/training/'+ID+'/answer-key.pdf');self.assertEqual(r.status_code,200)
        text='\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(r.data)).pages);self.assertIn('Training answer key',text)
    def test_csv_and_origin_guards(self):
        self.login();r=self.get('/api/training/'+ID+'/results.csv');self.assertEqual(r.status_code,200);self.assertIn("'=unsafe",r.get_data(as_text=True));self.assertIn("'+formula",r.get_data(as_text=True))
        r=self.client.post('/api/training/action',json={'op':'read','id':ID,'lesson':0},base_url=ORIGIN,headers={'Origin':'https://bad.invalid'});self.assertEqual(r.status_code,403)
        r=self.client.post('/api/training/action',json={'op':'backup'},base_url=ORIGIN,headers={'Origin':ORIGIN});self.assertEqual(r.status_code,400)
        self.p.allowed=False;self.assertEqual(self.get('/api/training/'+ID+'/guide.pdf').status_code,403)
    def test_seed_and_pdf(self):
        validate_course(COURSE);self.assertEqual(len(COURSE['questions']),20)
        pdf=PdfReader(io.BytesIO(guide_pdf(COURSE)));self.assertGreater(len(pdf.pages),3)
        for page in pdf.pages:self.assertGreaterEqual(len(page.images),1)
        text='\n'.join(p.extract_text() for p in pdf.pages)
        for term in ['Time in lieu','80%','Final knowledge test','quantity','Update preview']:self.assertIn(term,' '.join(text.split()))
    def test_backup_detects_score_completion_and_answer_tampering(self):
        # Produced by the independent SQL integration test, using the actual RPC.
        obj=json.loads(Path('/tmp/customu_training127_backup.json').read_text());validate_training(obj)
        for field,value in [('score',99),('passed',False),('answers',[None]*20)]:
            bad=copy.deepcopy(obj);bad['training_127']['attempts'][1][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):validate_training(bad)
        bad=copy.deepcopy(obj);bad['training_127']['progress'][0]['completed_at']=None
        with self.assertRaises(ValueError):validate_training(bad)
        validate_training({}) # Older HR backups remain valid.
if __name__=='__main__':unittest.main()
