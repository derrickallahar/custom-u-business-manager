import copy,io,json,unittest
from pathlib import Path
from production_app import create_app
from invoice_rules import validate_invoice_document
from payment_rules import validate_payments,payment_record
from adjustment_rules import validate_adjustments
from pypdf import PdfReader
from staff_access import allowed
F=json.loads(Path('/tmp/documents131_cases.json').read_text());ORIGIN='https://documents.example.invalid'
class Provider:
    def __init__(self):self.role='admin';self.permissions={};self.calls=[]
    def login(self,*a):return {'access_token':'fixture-token','expires_in':3600}
    def access(self,*a):return {'user_id':F['admin'],'email':'manager@example.invalid','role':self.role,'permissions':self.permissions}
    def call(self,path,token,body,limit=0):
        self.calls.append((path,body));p=body['payload']
        return json.dumps({'data':F['invoice'] if 'invoice' in path else F['beforeQuote']}).encode()
class Documents(unittest.TestCase):
    def client(self):
        p=Provider();a=create_app(p,ORIGIN,'',True,enforce_devices=False);c=a.test_client()
        c.post('/api/login',json={'email':'manager@example.invalid','password':'fixture-password'},headers={'Origin':ORIGIN},base_url=ORIGIN)
        return p,c
    def test_pdf_downloads_use_saved_revision(self):
        p,c=self.client()
        for kind,record in [('quotes',F['beforeQuote']),('invoices',F['invoice'])]:
            r=c.get('/api/'+kind+'/'+record['id']+'/pdf',base_url=ORIGIN)
            self.assertEqual(r.status_code,200,r.data[:200]);self.assertTrue(r.data.startswith(b'%PDF'))
            self.assertIn('attachment;',r.headers['Content-Disposition']);self.assertIn('_r'+str(record['version'])+'.pdf',r.headers['Content-Disposition'])
            pdf=PdfReader(io.BytesIO(r.data));text=' '.join(page.extract_text() for page in pdf.pages)
            self.assertIn(record['number'],text);self.assertIn('Scotiabank',text);self.assertTrue(any(page.images for page in pdf.pages))
            if kind=='invoices':
                self.assertIn('Corrected spelling',text);self.assertIn('BSD 11.00',text)
        source=c.get('/invoices/'+F['invoice']['id']+'/source-quote/print',base_url=ORIGIN)
        self.assertEqual(source.status_code,200);self.assertIn(b'Test quote',source.data);self.assertNotIn(b'Revised quote',source.data)
        p.role='office';p.permissions={'quotes.view':True}
        self.assertEqual(c.get('/api/invoices/'+F['invoice']['id']+'/pdf',base_url=ORIGIN).status_code,403)
        c=create_app(p,ORIGIN,'',True,enforce_devices=False).test_client()
        self.assertEqual(c.get('/api/quotes/'+F['beforeQuote']['id']+'/pdf',base_url=ORIGIN).status_code,401)
    def test_route_permissions_and_conversion(self):
        p,c=self.client();p.role='office';p.permissions={'quotes.view':True,'invoices.view':True,'quotes.edit':True,'invoices.edit':True}
        for area in ['quotes','invoices']:
            r=c.post('/api/'+area+'/save',json={'op':'amend','id':F['invoice']['id']},headers={'Origin':ORIGIN},base_url=ORIGIN)
            self.assertEqual(r.status_code,403)
            p.permissions[area+'.amend']=True
            r=c.post('/api/'+area+'/save',json={'op':'amend','id':F['invoice']['id']},headers={'Origin':ORIGIN},base_url=ORIGIN)
            self.assertEqual(r.status_code,200)
        p.permissions['invoices.create']=True
        r=c.post('/api/invoices/save',json={'op':'convert','quote_id':F['draft']['id'],'quote_version':1,'invoice_date':'2026-11-26'},headers={'Origin':ORIGIN},base_url=ORIGIN)
        self.assertEqual(r.status_code,200);self.assertIn('terms',p.calls[-1][1]['payload'])
        self.assertFalse(allowed({'role':'office','permissions':{'quotes.view':True,'quotes.approve':True}},'quotes',{'op':'amend'}))
    def test_audited_financial_history(self):
        obj=copy.deepcopy(F['snapshot']);validate_payments(obj);validate_adjustments(obj)
        for r in obj['invoices']:validate_invoice_document(r)
        payment_record(F['receipt']['payment'],F['receipt']['invoice'])
        bad=copy.deepcopy(obj);bad['payments'][0]['invoice_version']=999
        with self.assertRaises(ValueError):validate_payments(bad)
        bad=copy.deepcopy(obj);bad['invoices'][0]['quote_snapshot']['data']['lines'][0]['unit_price']='0.00'
        with self.assertRaises(ValueError):validate_payments(bad)
if __name__=='__main__':unittest.main()
