"""Validate training content and encrypted backup consistency."""
from datetime import datetime
import re

def need(ok):
    if not ok:raise ValueError('INVALID_TRAINING_BACKUP')
def uid(v):need(isinstance(v,str) and re.fullmatch(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}',v))
def stamp(v):
    need(isinstance(v,str));d=datetime.fromisoformat(v.replace('Z','+00:00'));need(d.tzinfo is not None);return d

def validate_course(d):
    need(isinstance(d,dict) and set(d)=={'title','edition','summary','estimated_minutes','pass_percent','lessons','questions'})
    def txt(s,n):need(isinstance(s,str) and 0<len(s.strip())<=n)
    for key,n in [('title',160),('edition',40),('summary',2000)]:txt(d[key],n)
    need(type(d['pass_percent']) is int and 1<=d['pass_percent']<=100 and type(d['estimated_minutes']) is int and 1<=d['estimated_minutes']<=999)
    need(isinstance(d['lessons'],list) and 1<=len(d['lessons'])<=30 and isinstance(d['questions'],list) and 1<=len(d['questions'])<=50)
    for x in d['lessons']:need(set(x)=={'title','body'});txt(x['title'],160);txt(x['body'],20000)
    for x in d['questions']:
        need(set(x)=={'prompt','options','correct_index','explanation'});txt(x['prompt'],1000);txt(x['explanation'],2000)
        need(isinstance(x['options'],list) and 2<=len(x['options'])<=6 and type(x['correct_index']) is int and 0<=x['correct_index']<len(x['options']))
        for s in x['options']:txt(s,500)

def validate_training(obj):
    if 'training_127' not in obj:return
    t=obj['training_127'];need(isinstance(t,dict) and set(t)=={'courses','assignments','progress','attempts','audit','requests'})
    for rows in t.values():need(isinstance(rows,list) and len(rows)<=200001)
    people={x['id'] for x in obj['hr_people']};courses={};progress={};attempts={}
    for c in t['courses']:
        uid(c['id']);need(c['id'] not in courses);validate_course(c['data']);need(c['status'] in ('draft','published','archived') and type(c['version']) is int and c['version']>0 and type(c['assigned_all']) is bool);stamp(c['created_at']);courses[c['id']]=c
    for p in t['progress']:
        key=(p['course_id'],p['employee_id']);need(key not in progress and key[0] in courses and key[1] in people)
        reads=p['read_lessons'];need(isinstance(reads,list) and len(reads)==len(set(reads)) and all(type(i) is int and 0<=i<len(courses[key[0]]['data']['lessons']) for i in reads));stamp(p['started_at']);progress[key]=p
    seen=set()
    for a in t['attempts']:
        uid(a['id']);need(a['id'] not in seen);seen.add(a['id']);key=(a['course_id'],a['employee_id']);need(key in progress)
        qs=courses[key[0]]['data']['questions'];answers=a['answers'];need(isinstance(answers,list) and len(answers)==len(qs) and all(type(n) is int and 0<=n<len(q['options']) for q,n in zip(qs,answers)))
        count=sum(n==q['correct_index'] for q,n in zip(qs,answers));score=count*100//len(qs);passed=count*100>=courses[key[0]]['data']['pass_percent']*len(qs)
        need(a['correct_count']==count and a['question_count']==len(qs) and a['score']==score and a['passed'] is passed);stamp(a['submitted_at']);attempts.setdefault(key,[]).append(a)
    for key,p in progress.items():
        aa=attempts.get(key,[]);passed=[x for x in aa if x['passed']]
        need(p['best_score']==(max(x['score'] for x in aa) if aa else None))
        need(p['completed_at']==(min(passed,key=lambda x:stamp(x['submitted_at']))['submitted_at'] if passed else None))
        if aa:need(len(p['read_lessons'])==len(courses[key[0]]['data']['lessons']))
    seen=set()
    for a in t['assignments']:
        key=(a['course_id'],a['employee_id']);need(key not in seen and key[0] in courses and key[1] in people);seen.add(key);uid(a['assigned_by']);stamp(a['assigned_at'])
    for a in t['audit']:need(a['course_id'] in courses);uid(a['actor_id']);stamp(a['happened_at'])
    for r in t['requests']:uid(r['actor_id']);uid(r['request_id']);need(r['request_id']==r['payload']['request_id']);stamp(r['created_at'])
