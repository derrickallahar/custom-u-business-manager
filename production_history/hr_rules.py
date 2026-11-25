"""HR time calculations and backup audit replay. No inferred payroll rates."""
from datetime import datetime,timezone,timedelta,time
from zoneinfo import ZoneInfo
from decimal import Decimal
import re

KINDS={'shift','early','leave','kpi','policy','ack','manager','device'}
def need(value):
    if not value:raise ValueError('INVALID_HR_DATA')
def stamp(value):
    need(isinstance(value,str));d=datetime.fromisoformat(value.replace('Z','+00:00'));need(d.tzinfo is not None);return d
def uid(value):need(isinstance(value,str) and re.fullmatch(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}',value))
def shift_totals(data,as_of):
    now=stamp(as_of) if isinstance(as_of,str) else as_of
    scheduled=stamp(data['scheduled_start']);pairs=[data['correction']] if data.get('correction') else data['intervals']
    seconds=Decimal(0);weekend_seconds=Decimal(0);previous=None;needs_review=False
    weekend_policy=data.get('time_policy')=='weekends_1153';nassau=ZoneInfo('America/Nassau')
    for pair in pairs:
        start=stamp(pair['in']);end=stamp(pair['out']) if pair['out'] else now
        need(end>=start and (previous is None or start>=previous))
        if (end-start).total_seconds()>16*3600:needs_review=True
        previous=end
        delta=max(Decimal(0),Decimal(str((end-max(start,scheduled)).total_seconds())))
        seconds+=delta
        if weekend_policy:
            cursor=max(start,scheduled).astimezone(timezone.utc);end_utc=end.astimezone(timezone.utc)
            while cursor<end_utc:
                local=cursor.astimezone(nassau)
                boundary=min(end_utc,datetime.combine(local.date()+timedelta(days=1),time(),nassau).astimezone(timezone.utc))
                if local.weekday()>=5:weekend_seconds+=Decimal(str((boundary-cursor).total_seconds()))
                cursor=boundary
    minutes=int(seconds//60)
    overtime=int((weekend_seconds+max(Decimal(0),seconds-weekend_seconds-480*60))//60)
    return {'credited_seconds':float(seconds),'worked_minutes':minutes,'regular_minutes':minutes-overtime,'overtime_minutes':overtime,'needs_review':needs_review,'provisional':data['state']=='in'}
def check_record(row):
    need(set(row)=={'id','kind','employee_id','data','version','created_at','updated_at'})
    uid(row['id']);need(row['kind'] in KINDS and type(row['version']) is int and row['version']>0)
    need(stamp(row['updated_at'])>=stamp(row['created_at']));d=row['data'];need(isinstance(d,dict))
    if row['employee_id'] is not None:uid(row['employee_id'])
    if row['kind']=='shift':
        need(set(d)-{'lieu','time_policy'}=={'day','scheduled_start','regular_minutes','intervals','state','correction'} and d['regular_minutes']==480 and d['state'] in ('in','out'))
        if 'time_policy' in d:need(d['time_policy']=='weekends_1153')
        need(isinstance(d['intervals'],list) and 1<=len(d['intervals'])<=100)
        for i,pair in enumerate(d['intervals']):
            need(set(pair)=={'in','out'});stamp(pair['in'])
            if pair['out'] is not None:need(stamp(pair['out'])>=stamp(pair['in']))
            else:need(i==len(d['intervals'])-1)
        if d['correction'] is not None:
            c=d['correction'];need(set(c)=={'in','out','reason','by','at'} and c['reason']);uid(c['by']);stamp(c['at']);need(stamp(c['out'])>=stamp(c['in']))
        else:need((d['intervals'][-1]['out'] is None)==(d['state']=='in'))
        shift_totals(d,max(stamp(row['updated_at']),stamp(d['intervals'][-1]['in'])))
        if 'lieu' in d:
            credit=d['lieu'];need(isinstance(credit,dict) and set(credit)=={'status','minutes','decided_by','decided_at','note'})
            need(credit['status'] in ('approved','declined','review_required') and type(credit['minutes']) is int and credit['minutes']>=0)
            uid(credit['decided_by']);stamp(credit['decided_at']);need(isinstance(credit['note'],str) and 1<=len(credit['note'])<=1000)
            if credit['status']=='approved':
                totals=shift_totals(d,row['updated_at']);need(d['state']=='out' and not totals['needs_review'] and credit['minutes']==totals['overtime_minutes'] and credit['minutes']>0)
            if credit['status']=='declined':need(credit['minutes']==0)
    elif row['kind'] in ('early','leave'):
        need(d.get('status') in ('pending','approved','declined','cancelled'))
        if row['kind']=='leave' and 'start_time' in d:
            need(d.get('leave_type')=='Personal' and isinstance(d['start_time'],str) and re.fullmatch(r'([01][0-9]|2[0-3]):[0-5][0-9]',d['start_time']))
        if row['kind']=='leave' and d.get('leave_type')=='Time in lieu':
            from datetime import date,timedelta
            start=date.fromisoformat(d['start_date']);end=date.fromisoformat(d['end_date']);need(0<=(end-start).days<=366)
            days=sum((start+timedelta(days=i)).weekday()<5 for i in range((end-start).days+1))
            need(type(d.get('lieu_minutes')) is int and 0<d['lieu_minutes']<=days*480)

    elif row['kind']=='policy':need(d.get('status') in ('draft','published') and d.get('title') and d.get('body') and d.get('edition'))
    elif row['kind']=='ack':uid(d['policy_id']);stamp(d['acknowledged_at'])
    elif row['kind'] in ('manager','device'):need(type(d.get('active')) is bool)
    elif row['kind']=='kpi':need(Decimal(d['target'])>=0 and Decimal(d['actual'])>=0 and d['direction'] in ('at_least','at_most'))
    if row['kind']=='device':need(re.fullmatch('[a-f0-9]{64}',d.get('digest','')) and d.get('name'))
def validate_hr(obj):
    from training_rules import validate_training
    validate_training(obj)
    from team_rules import validate_team
    validate_team(obj)
    people=obj['hr_people'];need(isinstance(people,list) and len(people)<=1000);people_ids=set()
    for p in people:
        need(set(p)=={'id','email','role'});uid(p['id']);need(p['id'] not in people_ids and isinstance(p['email'],str) and len(p['email'])<=254 and p['role'] in ('admin','office','sales','production'));people_ids.add(p['id'])
    rows=obj['hr_records'];audit=obj['hr_audit'];receipts=obj['hr_requests']
    need(isinstance(rows,list) and len(rows)<=100000 and isinstance(audit,list) and len(audit)<=100001 and isinstance(receipts,list) and len(receipts)<=100001)
    actual={}
    for r in rows:check_record(r);need(r['id'] not in actual);actual[r['id']]=r
    latest={};history={};seen=set()
    for a in sorted(audit,key=lambda x:x['id']):
        need(set(a)=={'id','record_id','actor_id','happened_at','before_record','after_record'} and type(a['id']) is int and a['id']>0 and a['id'] not in seen);seen.add(a['id']);uid(a['actor_id']);stamp(a['happened_at'])
        before=a['before_record'];after=a['after_record'];check_record(after);need(after['id']==a['record_id'] and latest.get(a['record_id'])==before)
        need(after['version']==(before['version']+1 if before else 1))
        if before:need(all(after[k]==before[k] for k in ('id','kind','employee_id','created_at')))
        need(after['updated_at']==a['happened_at']);latest[a['record_id']]=after;history[(a['actor_id'],after['id'],after['version'])]=after
    need(latest==actual)
    seen=set()
    for r in receipts:
        need(set(r)=={'actor_id','request_id','payload','result','created_at'});uid(r['actor_id']);uid(r['request_id']);stamp(r['created_at']);key=(r['actor_id'],r['request_id']);need(key not in seen);seen.add(key)
        need(r['payload']['request_id']==r['request_id'] and isinstance(r['result'],dict) and 'data' in r['result'])
        check_record(r['result']['data']);need(history.get((r['actor_id'],r['result']['data']['id'],r['result']['data']['version']))==r['result']['data'])

def lieu_balances(records):
    balances={}
    for r in records:
        emp=r.get('employee_id')
        if not emp:continue
        b=balances.setdefault(emp,{'employee_id':emp,'approved_minutes':0,'used_minutes':0,'pending_minutes':0,'available_minutes':0});d=r['data']
        if r['kind']=='shift' and d.get('lieu',{}).get('status')=='approved':b['approved_minutes']+=d['lieu']['minutes']
        if r['kind']=='leave' and d.get('leave_type')=='Time in lieu':
            if d['status']=='approved':b['used_minutes']+=d['lieu_minutes']
            if d['status']=='pending':b['pending_minutes']+=d['lieu_minutes']
    for b in balances.values():b['available_minutes']=b['approved_minutes']-b['used_minutes']
    return list(balances.values())
