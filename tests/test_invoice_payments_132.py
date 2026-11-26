import base64,copy,hashlib,io,json,unittest
from pathlib import Path
from unittest.mock import patch
from pypdf import PdfReader
from invoice_payment_summary import payment_view
from invoice_print import render_invoice
from document_pdf import render_document
from production_app import create_app

F=json.loads(Path('/tmp/documents131_cases.json').read_text())
CASES=json.loads(Path('/tmp/invoice_payments132_cases.json').read_text())
ORIGIN='https://payments.example.invalid'
class Provider:
    def __init__(self):self.result=copy.deepcopy(CASES['partial']);self.role='admin';self.permissions={};self.calls=[];self.retained=None
    def login(self,*args):return {'access_token':'fixture-token','expires_in':3600}
    def access(self,*args):return {'user_id':F['admin'],'email':'test@example.invalid','role':self.role,'permissions':self.permissions}
    def call(self,path,token,body,limit=0):
        p=body['payload'];self.calls.append((path,p))
        if 'custom_u_invoices_114' in path:return json.dumps(self.result).encode()
        if 'custom_u_quotes_097' in path:return json.dumps({'data':F['beforeQuote']}).encode()
        if 'custom_u_email_109' in path:
            if p['op']=='signed':p=json.loads(p['message'])['payload']
            if p['op']=='health':return b'{"ready":true}'
            if p['op']=='list':return b'{"data":[]}'
            if p['op']=='get':return json.dumps({'data':self.retained}).encode()
        raise AssertionError((path,p))
class PaymentDisplay(unittest.TestCase):
    def view(self,name):
        c=CASES[name];return payment_view(c['data'],c['payment_summary'])
    def test_status_and_dates(self):
        self.assertIsNone(self.view('draft'))
        for name,status in [('unpaid','Unpaid'),('partial','Partially paid'),('full','Paid in full'),('reversed','Partially paid'),('refund_due','Refund due'),('credited','Credited in full')]:
            v=self.view(name);self.assertEqual(v['status'],status)
            self.assertEqual(v['date_paid'],'26 Nov 2026' if name=='full' else '')
        self.assertEqual(self.view('partial')['last_payment_date'],'24 Nov 2026')
        c=copy.deepcopy(CASES['full']);c['data']['is_test']=True
        self.assertTrue(payment_view(c['data'],c['payment_summary'])['status'].startswith('Test —'))
        c=copy.deepcopy(CASES['partial']);s=c['payment_summary'];s.update(credit_cents=1200,balance_cents=0)
        v=payment_view(c['data'],s);self.assertEqual(v['status'],'Settled — payments and credits');self.assertEqual(v['date_paid'],'')
        c=copy.deepcopy(CASES['unpaid']);c['data']['quote_snapshot']['data']['total_cents']=0;c['payment_summary'].update(total_cents=0,balance_cents=0)
        self.assertEqual(payment_view(c['data'],c['payment_summary'])['status'],'No amount due')
    def test_inconsistent_summary_fails(self):
        for key,value in [('invoice_id','other'),('invoice_version',999),('ledger_version',True),('balance_cents',-1),('total_cents',1),('paid_cents',9999),('credit_cents',9999),('refund_cents',9999)]:
            c=copy.deepcopy(CASES['full']);c['payment_summary'][key]=value
            with self.assertRaises(ValueError,msg=key):payment_view(c['data'],c['payment_summary'])
        for key,value in [('date','2026-02-30'),('date','2026-1-1'),('number','<script>'),('amount_cents',False)]:
            c=copy.deepcopy(CASES['full']);c['payment_summary']['payments'][0][key]=value
            with self.assertRaises(ValueError,msg=key):payment_view(c['data'],c['payment_summary'])
        for mutate in [lambda p:p.append(p[0]),lambda p:p.reverse(),lambda p:p.clear()]:
            c=copy.deepcopy(CASES['full']);mutate(c['payment_summary']['payments'])
            with self.assertRaises(ValueError):payment_view(c['data'],c['payment_summary'])
    def test_pdf_and_html(self):
        output=Path('/tmp/payment132');output.mkdir(exist_ok=True)
        for name,c in CASES.items():
            before=copy.deepcopy(c);pdf=render_document('invoice',c['data'],c['payment_summary']);html=render_invoice(c['data'],c['payment_summary']);self.assertEqual(c,before)
            self.assertEqual(pdf,render_document('invoice',c['data'],c['payment_summary']))
            doc=PdfReader(io.BytesIO(pdf));text=' '.join(page.extract_text() for page in doc.pages)
            self.assertIn('Scotiabank',text);self.assertTrue(any(page.images for page in doc.pages))
            if name=='draft':self.assertNotIn('Payment status:',text)
            else:
                v=self.view(name);self.assertIn(v['status'],text);self.assertIn(v['status'],html)
                for p in v['payments']:self.assertIn(p['date_label'],text);self.assertIn(p['number'],text)
            if name=='full':self.assertIn('Date paid: 26 Nov 2026',text);self.assertIn('BSD 0.00',text)
            if name=='partial':self.assertIn('BSD 12.00',text)
            (output/(name+'.pdf')).write_bytes(pdf)
        self.assertIn('Payment status is not included',render_invoice(CASES['full']['data']))
        c=copy.deepcopy(CASES['full']);s=c['payment_summary'];s['payments']=[{'number':f'PAY-{n:03}','date':'2026-11-26','amount_cents':22} for n in range(100)]
        pdf=render_document('invoice',c['data'],s);doc=PdfReader(io.BytesIO(pdf));text=' '.join(p.extract_text() for p in doc.pages)
        self.assertGreater(len(doc.pages),2);self.assertIn('PAY-099',text);self.assertIn('Balance due',text)
        (output/'many-payments.pdf').write_bytes(pdf)
    def client(self):
        p=Provider()
        with patch.dict('os.environ',{'RESEND_API_KEY':'re_test_fixture_132','CUSTOMU_EMAIL_SIGNING_SECRET':'a'*64,'CUSTOMU_EMAIL_TEST_MODE':'1','CUSTOMU_EMAIL_TEST_RECIPIENT':'test@example.invalid'}):
            a=create_app(p,ORIGIN,'',True,enforce_devices=False)
        class NoEmail:
            def send(self,row):raise AssertionError('No email may be sent by this test')
        a.extensions['email_transport']=NoEmail();c=a.test_client()
        c.post('/api/login',json={'email':'test@example.invalid','password':'test-password'},headers={'Origin':ORIGIN},base_url=ORIGIN)
        return p,c,a
    def test_routes_and_missing_ledger(self):
        p,c,a=self.client();i=p.result['data'];base='/api/invoices/'+i['id']
        self.assertEqual(c.get(base,base_url=ORIGIN).json['payment_view']['status'],'Partially paid')
        self.assertIn(b'24 Nov 2026',c.get('/invoices/'+i['id']+'/print',base_url=ORIGIN).data)
        r=c.get(base+'/pdf',base_url=ORIGIN);self.assertEqual(r.status_code,200);self.assertIn('attachment;',r.headers['Content-Disposition'])
        p.role='office';p.permissions={'invoices.view':True}
        self.assertEqual(c.get(base,base_url=ORIGIN).status_code,200)
        p.permissions={};self.assertEqual(c.get(base,base_url=ORIGIN).status_code,403)
        p.role='admin';p.result.pop('payment_summary')
        self.assertEqual(c.get(base+'/pdf',base_url=ORIGIN).status_code,503)
        self.assertEqual(c.get(base,base_url=ORIGIN).json['error'],'INVOICE_PAYMENTS_UNAVAILABLE')
        self.assertEqual(a.test_client().get(base,base_url=ORIGIN).status_code,401)
    def test_review_detects_payment_change_and_keeps_old_pdf(self):
        p,c,a=self.client();i=p.result['data']
        body={'kind':'invoice','id':i['id'],'recipient':'test@example.invalid','subject':'Fixture invoice','message':'Test message'}
        preview=c.post('/api/email/preview',json=body,headers={'Origin':ORIGIN},base_url=ORIGIN)
        self.assertEqual(preview.status_code,200,preview.data);packet=preview.json;raw=base64.b64decode(packet['pdf_base64'])
        p.retained={**packet['data'],'pdf_base64':packet['pdf_base64']}
        p.result=copy.deepcopy(CASES['full'])
        fresh=c.post('/api/email/preview',json=body,headers={'Origin':ORIGIN},base_url=ORIGIN)
        self.assertEqual(fresh.status_code,200);self.assertNotEqual(fresh.json['data']['pdf_sha256'],packet['data']['pdf_sha256'])
        stale=c.post('/api/email/send',json={'review_token':packet['review_token'],'confirm':True},headers={'Origin':ORIGIN},base_url=ORIGIN)
        self.assertEqual(stale.status_code,409,stale.data);self.assertEqual(stale.json['error'],'EMAIL_DOCUMENT_CHANGED')
        old=c.get('/api/email/'+packet['data']['id']+'/pdf',base_url=ORIGIN)
        self.assertEqual(old.data,raw);self.assertIn('inline;',old.headers['Content-Disposition'])
        self.assertFalse(any('custom_u_invoices_098' in path for path,_ in p.calls))
        for name,value in CASES.items():value['payment_view']=payment_view(value['data'],value['payment_summary'])
        Path('/tmp/invoice_payments132_views.json').write_text(json.dumps(CASES))
if __name__=='__main__':unittest.main()
