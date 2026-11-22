"""Credit/refund validation and replay against the unchanged invoice/payment history."""
from datetime import date
from collections import defaultdict,Counter
import re
from quote_rules import need,text
from payment_rules import ident,timestamp,integer,METHODS
CREDIT_FIELDS={'id','serial','invoice_id','invoice_version','is_test','number','details','status','version','created_by','created_at','updated_by','updated_at'}
REFUND_FIELDS={'id','serial','invoice_id','invoice_version','is_test','number','details','status','version','created_by','created_at','reversed_by','reversed_at','reversal_reason'}
def day(v):
    need(isinstance(v,str) and re.fullmatch(r'20\d{2}-\d{2}-\d{2}',v) is not None);return date.fromisoformat(v)
def common(r,inv,fields,prefix):
    need(isinstance(r,dict) and set(r)==fields);ident(r['id']);ident(r['invoice_id']);ident(r['created_by']);timestamp(r['created_at'])
    need(inv['status']=='issued' and r['invoice_id']==inv['id'] and type(r['is_test']) is bool and r['is_test']==inv['is_test']);integer(r['invoice_version'],1);need(r['invoice_version']==inv['version'])
    integer(r['serial'],1,99999999);integer(r['version'],1,1000000);need(r['number']==('CU-TEST-' if r['is_test'] else 'CU-')+prefix+'-'+str(r['serial']).zfill(8))
def credit_record(r,inv):
    common(r,inv,CREDIT_FIELDS,'C');ident(r['updated_by']);need(timestamp(r['updated_at'])>=timestamp(r['created_at']));need(r['status'] in ('draft','issued'))
    d=r['details'];need(isinstance(d,dict) and set(d)=={'credit_date','reason','lines','net_cents','tax_cents','total_cents','prior_credit_cents'})
    need(day(d['credit_date'])>=day(inv['details']['invoice_date']));need(text(d['reason'],1000,True,True)==d['reason']);need(isinstance(d['lines'],list) and 1<=len(d['lines'])<=100)
    seen=[];net=tax=0
    for x in d['lines']:
        need(isinstance(x,dict) and set(x)=={'line_index','net_cents','tax_cents','total_cents','prior_net_cents','prior_tax_cents'});integer(x['line_index'],0,len(inv['quote_snapshot']['data']['lines'])-1)
        seen.append(x['line_index']);l=inv['quote_snapshot']['data']['lines'][x['line_index']]
        for k in ('net_cents','tax_cents','total_cents','prior_net_cents','prior_tax_cents'):integer(x[k])
        need(x['net_cents']>0 and x['prior_net_cents']+x['net_cents']<=l['net_cents'])
        need(x['prior_tax_cents']<=l['tax_cents']);need(x['tax_cents']==(2*l['tax_cents']*(x['prior_net_cents']+x['net_cents'])+l['net_cents'])//(2*l['net_cents'])-x['prior_tax_cents'])
        need(x['total_cents']==x['net_cents']+x['tax_cents']);net+=x['net_cents'];tax+=x['tax_cents']
    need(seen==sorted(set(seen)))
    for k in ('net_cents','tax_cents','total_cents','prior_credit_cents'):integer(d[k])
    need((net,tax,net+tax)==(d['net_cents'],d['tax_cents'],d['total_cents']));need(d['total_cents']+d['prior_credit_cents']<=inv['quote_snapshot']['data']['total_cents'])
    return r

def refund_record(r,inv):
    common(r,inv,REFUND_FIELDS,'F');d=r['details'];need(isinstance(d,dict) and set(d)=={'refund_date','amount_cents','method','reference','reason'});day(d['refund_date']);integer(d['amount_cents'],1,inv['quote_snapshot']['data']['total_cents']);need(d['method'] in METHODS)
    need(text(d['reference'],120)==d['reference'] and text(d['reason'],1000,True,True)==d['reason'])
    if r['status']=='recorded':need(r['version']==1 and r['reversed_by'] is None and r['reversed_at'] is None and r['reversal_reason']=='')
    else:
        need(r['status']=='reversed' and r['version']==2);ident(r['reversed_by']);need(timestamp(r['reversed_at'])>=timestamp(r['created_at']));need(text(r['reversal_reason'],500,True,True)==r['reversal_reason'])
    return r

def validate_adjustments(obj):
    invs={i['id']:i for i in obj['invoices']};records={};numbers=set();counts=Counter()
    for entity,name,limit,check in [('credit','credits',5000,credit_record),('refund','refunds',10000,refund_record)]:
        need(isinstance(obj[name],list) and len(obj[name])<=limit)
        for r in obj[name]:
            need(isinstance(r,dict) and r.get('invoice_id') in invs);check(r,invs[r['invoice_id']]);k=(entity,r['id']);need(k not in records and r['number'] not in numbers);numbers.add(r['number']);records[k]=r;counts[(entity,r['invoice_id'])]+=1
    need(all(n<=(200 if e=='credit' else 500) for (e,i),n in counts.items()))
    audit=obj['adjustment_audit'];need(isinstance(audit,list) and len(audit)<=100000);seen=set();latest={};groups=defaultdict(list);lastpv=defaultdict(int)
    for a in sorted(audit,key=lambda a:a.get('id',0) if isinstance(a,dict) and type(a.get('id')) is int else 0):
        need(isinstance(a,dict) and set(a)=={'id','invoice_id','entity','entity_id','operation','payment_version','actor_id','happened_at','before_record','after_record'})
        integer(a['id'],1,9007199254740991);need(a['id'] not in seen);seen.add(a['id']);ident(a['actor_id']);timestamp(a['happened_at']);integer(a['payment_version'],0,1000)
        iid=a['invoice_id'];k=(a['entity'],a['entity_id']);need(k in records and iid==records[k]['invoice_id']);need(a['payment_version']>=lastpv[iid]);lastpv[iid]=a['payment_version']
        b=a['before_record'];r=a['after_record'];need(b==latest.get(k) and r['id']==a['entity_id']);(credit_record if a['entity']=='credit' else refund_record)(r,invs[iid])
        if b is None:
            need(r['version']==1 and r['created_by']==a['actor_id'] and timestamp(r['created_at'])==timestamp(a['happened_at']))
            need((a['entity'],a['operation'],r['status']) in (('credit','create','draft'),('refund','record','recorded')))
        else:
            need(r['version']==b['version']+1)
            if a['entity']=='credit':
                need(b['status']=='draft' and (a['operation'],r['status']) in (('save','draft'),('issue','issued')))
                mutable={'version','updated_at','updated_by','details'} if a['operation']=='save' else {'version','updated_at','updated_by','status'}
            else:
                need(a['operation']=='reverse' and b['status']=='recorded' and r['status']=='reversed');mutable={'version','status','reversed_at','reversed_by','reversal_reason'}
                need(r['reversed_by']==a['actor_id'] and timestamp(r['reversed_at'])==timestamp(a['happened_at']))
            need({k:v for k,v in b.items() if k not in mutable}=={k:v for k,v in r.items() if k not in mutable})
        if a['entity']=='credit':need(r['updated_by']==a['actor_id'] and timestamp(r['updated_at'])==timestamp(a['happened_at']))
        latest[k]=r;groups[(iid,a['payment_version'])].append(a)
    need(latest==records)
    # Merge adjustment events with each invoice's original payment audit sequence.
    # The shared invoice row lock makes payment_version a stable ordering boundary.
    pa=defaultdict(list)
    for a in obj['payment_audit']:pa[a['invoice_id']].append(a)
    for iid,inv in invs.items():
        active_payments={};issued={};active_refunds={};net_by_line=Counter();tax_by_line=Counter();total=inv['quote_snapshot']['data']['total_cents']
        def totals():return sum(p['details']['amount_cents'] for p in active_payments.values()),sum(c['details']['total_cents'] for c in issued.values()),sum(r['details']['amount_cents'] for r in active_refunds.values())
        def apply(pv):
            for a in groups.pop((iid,pv),[]):
                r=a['after_record'];paid,credits,refunded=totals()
                if a['entity']=='credit':
                    d=r['details'];need(d['prior_credit_cents']==credits)
                    for x in d['lines']:need((x['prior_net_cents'],x['prior_tax_cents'])==(net_by_line[x['line_index']],tax_by_line[x['line_index']]))
                    if a['operation']=='issue':
                        issued[r['id']]=r
                        for x in d['lines']:net_by_line[x['line_index']]+=x['net_cents'];tax_by_line[x['line_index']]+=x['tax_cents']
                elif a['operation']=='record':need(r['details']['amount_cents']<=max(paid-refunded-total+credits,0));active_refunds[r['id']]=r
                else:need(r['id'] in active_refunds);del active_refunds[r['id']]
                paid,credits,refunded=totals();need(0<=credits<=total and 0<=refunded<=min(paid,credits))
        apply(0)
        for a in sorted(pa[iid],key=lambda a:a['ledger_version']):
            paid,credits,refunded=totals();r=a['after_record'];amount=r['details']['amount_cents']
            if a['operation']=='record':need(amount<=max(total-credits-paid+refunded,0));active_payments[r['id']]=r
            else:need(r['id'] in active_payments and paid-amount>=refunded);del active_payments[r['id']]
            apply(a['ledger_version'])
    need(not groups);return obj
