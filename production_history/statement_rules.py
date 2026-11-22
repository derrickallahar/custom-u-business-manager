"""Current balances and due-date ageing. All values are integer BSD cents."""
from datetime import date
import re
from collections import defaultdict
from quote_rules import need,text
from payment_rules import integer,ident,timestamp

BUCKETS=('current_cents','days_1_30_cents','days_31_60_cents','days_61_90_cents','days_91_plus_cents')
AMOUNTS=('total_cents','credit_cents','payment_cents','refund_cents','adjusted_cents','net_paid_cents','balance_cents','refund_due_cents')+BUCKETS
SCOPE='Current finalised invoices created in Custom U only. ShopVox archive balances and draft documents are excluded. Refunds due remain separate from amounts owed on other invoices. No late fees are calculated.'

def day(v):
    need(isinstance(v,str) and len(v)==10);d=date.fromisoformat(v);need(d.isoformat()==v);return d

def build_101(raw,test_mode):
    need(isinstance(raw,dict) and raw.get('format')=='custom-u-statements-101' and type(raw.get('test_mode')) is bool and raw['test_mode']==test_mode)
    as_of=day(raw['as_of']);timestamp(raw['generated_at']);need(isinstance(raw['invoices'],list) and len(raw['invoices'])<=5000)
    out={k:raw[k] for k in ('format','test_mode','as_of','generated_at','seller')};out['scope']=SCOPE;rows=[];seen=set();by_id={}
    for source in raw['invoices']:
        r=dict(source);ident(r['id']);ident(r['customer_id']);need(r['id'] not in seen);seen.add(r['id']);need(type(r['is_test']) is bool and r['is_test']==test_mode)
        for k in ('number','customer_name','invoice_customer_name','title'):need(text(r[k],200,k=='title',True)==r[k])
        need(bool(re.fullmatch(r'CU-TEST-I-[0-9]{8}',r['number'])) if test_mode else bool(re.fullmatch(r'(?:CU-I-[0-9]{8}|[1-9][0-9]{0,7})',r['number'])));day(r['invoice_date']);due=day(r['due_date']);need(due>=day(r['invoice_date']))
        for k in ('total_cents','credit_cents','payment_cents','refund_cents'):integer(r[k])
        t,c,p,f=(r[k] for k in ('total_cents','credit_cents','payment_cents','refund_cents'));need(c<=t and p<=t and f<=min(p,c))
        r.update(adjusted_cents=t-c,net_paid_cents=p-f,balance_cents=max(t-c-p+f,0),refund_due_cents=max(p-f-t+c,0))
        age=max((as_of-due).days,0) if r['balance_cents'] else 0;r['days_overdue']=age
        bucket=BUCKETS[0 if age==0 else 1 if age<=30 else 2 if age<=60 else 3 if age<=90 else 4]
        r.update({k:r['balance_cents'] if k==bucket else 0 for k in BUCKETS});rows.append(r);by_id[r['id']]=r
    rows.sort(key=lambda r:(r['due_date'],r['number']));out['invoices']=rows;out['totals']=totals(rows)
    if 'customer_id' in raw:
        ident(raw['customer_id']);need(rows and all(r['customer_id']==raw['customer_id'] for r in rows));need(isinstance(raw['customer'],dict));need(text(raw['customer']['name'],200,False,True)==raw['customer']['name'])
        out.update(customer_id=raw['customer_id'],customer=raw['customer']);need(isinstance(raw['activity'],list) and len(raw['activity'])<=5000)
        activity=[];keys=set();sums=defaultdict(lambda:defaultdict(int))
        for source in raw['activity']:
            a=dict(source);ident(a['id']);ident(a['invoice_id']);need(a['invoice_id'] in by_id);r=by_id[a['invoice_id']];need(a['invoice_number']==r['number']);day(a['effective_date']);timestamp(a['recorded_at'])
            need(a['kind'] in ('invoice','credit','payment','refund'));key=(a['kind'],a['id']);need(key not in keys);keys.add(key);need(text(a['number'],80,False,True)==a['number']);need(text(a['reference'],120)==a['reference']);integer(a['amount_cents'])
            need(a['status'] in (('issued',) if a['kind'] in ('invoice','credit') else ('recorded','reversed')))
            if a['kind']=='invoice':need(a['id']==r['id'] and a['number']==r['number'])
            active=a['status']!='reversed';amount=a['amount_cents'] if active else 0;sums[r['id']][a['kind']]+=amount
            a['effect_cents']=amount*(-1 if a['kind'] in ('credit','payment') else 1);activity.append(a)
        for r in rows:
            need(('invoice',r['id']) in keys)
            for kind,field in [('invoice','total_cents'),('credit','credit_cents'),('payment','payment_cents'),('refund','refund_cents')]:need(sums[r['id']][kind]==r[field])
        activity.sort(key=lambda a:(a['effective_date'],a['recorded_at'],a['kind'],a['id']));out['activity']=activity
    return out

def totals(rows):
    return {**{k:sum(r[k] for r in rows) for k in AMOUNTS},'invoice_count':len(rows),'customer_count':len({r['customer_id'] for r in rows}),'overdue_cents':sum(r['balance_cents'] for r in rows if r['days_overdue']>0)}

def report(data,q='',status='all',page=1):
    need(isinstance(q,str) and len(q)<=200 and not any(ord(c)<32 for c in q));need(status in ('all','open','overdue','refund_due'));need(type(page) is int and 1<=page<=100000)
    query=q.strip().casefold();rows=[r for r in data['invoices'] if (not query or query in ' '.join(r[k] for k in ('customer_name','invoice_customer_name','number','title')).casefold()) and (status=='all' or status=='open' and r['balance_cents']>0 or status=='overdue' and r['days_overdue']>0 or status=='refund_due' and r['refund_due_cents']>0)]
    groups=defaultdict(list)
    for r in rows:groups[r['customer_id']].append(r)
    customers=[{'id':k,'name':v[0]['customer_name'],**totals(v)} for k,v in groups.items()];customers.sort(key=lambda x:(x['name'].casefold(),x['id']))
    return {**{k:data[k] for k in ('format','test_mode','as_of','generated_at','seller','scope')},'q':q.strip(),'status':status,'totals':totals(rows),'total':len(customers),'page':page,'data':customers[(page-1)*50:page*50],'all_customers':customers}


def build(raw,test_mode):
    if raw.get('format')!='custom-u-statements-111':return build_101(raw,test_mode)
    from legacy_rules import validate_state
    state=raw['legacy'];need(state['mode']==('test' if test_mode else 'live'))
    legacy=validate_state(state);base={k:v for k,v in raw.items() if k!='legacy'};base['format']='custom-u-statements-101'
    customer=raw.get('customer_id')
    if customer and not base['invoices']:
        plain={k:v for k,v in base.items() if k not in ('customer_id','customer','activity')};out=build_101(plain,test_mode)
        ident(customer);need(text(raw['customer']['name'],200,False,True)==raw['customer']['name']);need(base['activity']==[])
        out.update(customer_id=customer,customer=raw['customer'],activity=[])
    else:out=build_101(base,test_mode)
    out['format']='custom-u-statements-111'
    out['scope']='Current finalised Custom U invoices plus imported ShopVox opening balances in the selected mode. Paid and credited figures include retained source totals and later records. Rehearsals are excluded. Refunds due remain separate. No late fees are calculated.'
    seen={x['id'] for x in out['invoices']};as_of=day(out['as_of'])
    for item in legacy:
        if customer and item['customer_id']!=customer:continue
        need(item['id'] not in seen);seen.add(item['id'])
        r={'id':item['id'],'number':'ShopVox '+item['number'],'customer_id':item['customer_id'],'customer_name':raw['customer']['name'] if customer else item['customer_name'],'invoice_customer_name':item['source_customer'],'title':'Imported opening balance · '+state['book']['as_of'],'invoice_date':item['invoice_date'],'due_date':item['due_date'],'is_test':test_mode,'source':'legacy','total_cents':item['total_cents'],'credit_cents':item['credit_cents']+item['subsequent_credit_cents'],'payment_cents':item['paid_cents']+item['subsequent_paid_cents'],'refund_cents':0,'balance_cents':item['remaining_cents'],'refund_due_cents':0}
        r['adjusted_cents']=r['total_cents']-r['credit_cents'];r['net_paid_cents']=r['payment_cents'];need(r['adjusted_cents']-r['net_paid_cents']==r['balance_cents'])
        age=max((as_of-day(r['due_date'])).days,0) if r['balance_cents'] else 0;r['days_overdue']=age
        bucket=BUCKETS[0 if age==0 else 1 if age<=30 else 2 if age<=60 else 3 if age<=90 else 4];r.update({k:r['balance_cents'] if k==bucket else 0 for k in BUCKETS});out['invoices'].append(r)
        if customer:
            out['activity'].append({'id':r['id'],'invoice_id':r['id'],'invoice_number':r['number'],'kind':'legacy_opening','number':r['number'],'effective_date':state['book']['as_of'],'recorded_at':state['book']['created_at'],'amount_cents':item['opening_cents'],'effect_cents':item['opening_cents'],'status':'issued','reference':'Opening balance after historical payments and credits'})
            for e in item['activity']:
                out['activity'].append({'id':e['id'],'invoice_id':r['id'],'invoice_number':r['number'],'kind':'legacy_'+e['kind'],'number':e['reference'],'effective_date':e['effective_date'],'recorded_at':e['created_at'],'amount_cents':e['amount_cents'],'effect_cents':e['amount_cents']*(1 if e['kind']=='reversal' else -1),'status':'recorded','reference':e['reason']+(' (reversed by a later correction)' if e['reversed'] else '')})
    need(len(out['invoices'])<=6000)
    out['invoices'].sort(key=lambda x:(x['due_date'],x['number']));out['totals']=totals(out['invoices'])
    if customer:
        need(out['invoices'] and len(out['activity'])<=10000)
        out['activity'].sort(key=lambda a:(a['effective_date'],a['recorded_at'],a['kind'],a['id']))
        need(sum(a['effect_cents'] for a in out['activity'])==out['totals']['balance_cents']-out['totals']['refund_due_cents'])
    return out
