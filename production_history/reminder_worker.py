"""One bounded cron invocation. Durable claims prevent automatic duplicate attempts."""
import base64,hashlib,hmac,json,os,time,uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from email_delivery import Settings,Resend,address,canonical,checked_pdf
from reminder_rules import settings,invoice,PACKET
from reminder_pdf import render

class ReminderError(Exception):pass
class Runner:
    def __init__(self,provider,config=None,transport=None):
        self.provider=provider;self.config=config or Settings();self.transport=transport or Resend(self.config.api_key)
        self.live_enabled=os.getenv('CUSTOMU_REMINDER_LIVE_ENABLED','')=='1'
        if not self.config.ready:raise ReminderError('EMAIL_NOT_CONFIGURED')
    def call(self,command):
        c=self.config
        env={'command':command,'expires':int(time.time())+90,'test_mode':c.test_mode,'test_to':c.test_to,'sender':c.sender,'reply_to':c.reply_to,'live_enabled':self.live_enabled}
        message=canonical(env);signature=hmac.new(bytes.fromhex(c.secret),('reminder112\n'+message).encode(),hashlib.sha256).hexdigest()
        raw=self.provider.call('/rest/v1/rpc/custom_u_reminder_worker_112',None,{'payload':{'message':message,'signature':signature}},limit=10000000)
        result=json.loads(raw)
        if not isinstance(result,dict):raise ReminderError('REMINDER_RESPONSE_INVALID')
        if result.get('error'):raise ReminderError(result['error'])
        return result
    def packet(self,candidate,today,mode):
        row=invoice(candidate['invoice']);address(row['recipient']);ident=str(uuid.uuid4());stage=candidate['stage'];test=mode=='test'
        raw=render(row,stage,today,test);prefix='TEST - ' if test else ''
        message=('TEST DELIVERY - for internal checking only.\n\n' if test else '')+'Hello,\n\nOur records show an outstanding balance of BSD '+format(row['balance_cents']/100,',.2f')+' for invoice '+row['number']+', due '+row['due_date']+'.\n\nPlease arrange payment. If you have already paid, please reply with the payment reference so we can check our records.\n\nKind regards,\nCustom U'
        return {'id':ident,'invoice':row,'stage':stage,'recipient':self.config.test_to if test else row['recipient'],'sender':self.config.sender,'reply_to':self.config.reply_to,'subject':prefix+'Custom U payment reminder: '+row['number'],'message':message,'pdf_filename':'CustomU_Reminder_'+ident+'.pdf','pdf_sha256':hashlib.sha256(raw).hexdigest(),'pdf_base64':base64.b64encode(raw).decode()}
    def run(self,mode='test',manual=False,access_check=None,max_count=20):
        if mode not in ('test','live') or manual and mode!='test':raise ReminderError('INVALID_MODE')
        if mode=='live' and (not self.live_enabled or self.config.test_mode):raise ReminderError('REMINDER_LIVE_DISABLED')
        report={'considered':0,'accepted':0,'rejected':0,'uncertain':0,'skipped':0,'state':'complete'}
        state=self.call({'op':'state','mode':mode});cfg=settings(state['settings'])
        if not cfg['enabled']:return {**report,'state':'paused'}
        if not manual and state['local_hour']<cfg['send_hour']:return {**report,'state':'before_send_time'}
        for candidate in [x for x in state['candidates'] if x['reason']=='DUE'][:max(1,min(20,max_count))]:
            report['considered']+=1
            if access_check:access_check()
            try:packet=self.packet(candidate,state['today'],mode)
            except ValueError:report['skipped']+=1;continue
            try:claim=self.call({'op':'claim','mode':mode,'id':packet['id'],'settings_version':cfg['version'],'manual':bool(manual),'delivery':packet})
            except ReminderError as exc:
                if str(exc) in ('REMINDER_NO_LONGER_DUE','VERSION_CONFLICT','REMINDERS_PAUSED','BEFORE_SEND_TIME','SCHEDULE_OWNER_INACTIVE'):report['skipped']+=1;continue
                raise
            if claim.get('send_now') is not True:report['skipped']+=1;continue
            row=claim.get('data',{})
            if any(row.get(k)!=v for k,v in packet.items()) or row.get('state')!='attempted':raise ReminderError('REMINDER_CLAIM_UNCERTAIN')
            checked_pdf(row)
            if access_check:access_check()
            status,provider_id,error_code=self.transport.send(row)
            try:self.call({'op':'settle','mode':mode,'id':row['id'],'state':status,'provider_id':provider_id,'error_code':error_code})
            except Exception:raise ReminderError('REMINDER_RESULT_UNCERTAIN') from None
            report[status]+=1
        return report

def main():
    # A job must be explicitly enabled. Creating a component alone sends nothing.
    if os.getenv('CUSTOMU_REMINDER_WORKER_ENABLED','')!='1':print('REMINDER_WORKER_DISABLED');return 0
    try:
        from production_app import Supabase
        provider=Supabase(os.getenv('CUSTOMU_PRODUCTION_PUBLISHABLE_KEY',''))
        mode=os.getenv('CUSTOMU_REMINDER_MODE','test')
        report=Runner(provider).run(mode,max_count=1 if mode=='test' else 20)
        print('Reminder run:',canonical(report));return 0
    except Exception:
        # No customer data, signing keys or provider response bodies in logs.
        print('REMINDER_RUN_FAILED - check app reminder history and worker configuration. No automatic resend of attempted stages.');return 1
if __name__=='__main__':raise SystemExit(main())
