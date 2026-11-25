"""Attendance evidence and early-work review, independent of payroll rates/credits."""
from datetime import datetime,timezone,timedelta,time
from zoneinfo import ZoneInfo
from decimal import Decimal

NASSAU=ZoneInfo('America/Nassau')
def stamp(v):return datetime.fromisoformat(v.replace('Z','+00:00')) if isinstance(v,str) else v
def attendance(data,as_of):
    now=stamp(as_of);scheduled=stamp(data['scheduled_start'])
    day=datetime.fromisoformat(data['day']);cutoff=datetime.combine(day.date(),time(9),NASSAU)
    weekday=day.weekday()<5;report=data.get('early_report');correction=data.get('correction')
    raw_early=unclassified=Decimal(0);long=False
    for p in data['intervals']:
        s=stamp(p['in']);e=stamp(p['out']) if p['out'] else now
        if weekday:
            raw_early+=max(Decimal(0),Decimal(str((min(e,cutoff)-s).total_seconds())))
            unclassified+=max(Decimal(0),Decimal(str((min(e,scheduled)-s).total_seconds())))
    reported=sum((Decimal(str((stamp(p['out'])-stamp(p['in'])).total_seconds())) for p in (report or {}).get('intervals',[])),Decimal(0))
    confirmed=bool(report and (report.get('review') or {}).get('decision')=='confirmed')
    status='corrected' if correction else ('confirmed_'+report['kind'] if confirmed else 'clarification' if report.get('review') else 'pending') if report else 'unreported' if unclassified>0 else 'not_required'
    unresolved=not correction and (bool(report and not confirmed) or bool(not report and unclassified>0))
    pairs=[correction] if correction else data['intervals']
    effective=[];previous=None
    for p in pairs:
        s=stamp(p['in']);e=stamp(p['out']) if p['out'] else now
        if e<s or (previous is not None and s<previous):raise ValueError('INVALID_HR_DATA')
        previous=e;long=long or (e-s).total_seconds()>57600
        begin=s if correction else max(s,cutoff if report else scheduled)
        if e>begin:effective.append((begin,e))
    if not correction and confirmed and report['kind']=='work':effective += [(stamp(p['in']),stamp(p['out'])) for p in report['intervals']]
    seconds=weekend=early=Decimal(0)
    for s,e in effective:
        seconds+=Decimal(str((e-s).total_seconds()))
        if weekday:early+=max(Decimal(0),Decimal(str((min(e,cutoff)-s).total_seconds())))
        cursor=s.astimezone(timezone.utc);end=e.astimezone(timezone.utc)
        while data.get('time_policy')=='weekends_1153' and cursor<end:
            local=cursor.astimezone(NASSAU);boundary=min(end,datetime.combine(local.date()+timedelta(days=1),time(),NASSAU).astimezone(timezone.utc))
            if local.weekday()>=5:weekend+=Decimal(str((boundary-cursor).total_seconds()))
            cursor=boundary
    minutes=int(seconds//60);candidate=int((weekend+max(Decimal(0),seconds-weekend-28800))//60)
    return {'credited_seconds':float(seconds),'worked_minutes':minutes,'regular_minutes':minutes-candidate,'overtime_minutes':candidate,
      'needs_review':bool(long or unresolved),'provisional':data['state']=='in','early_review_status':status,
      'early_punch_minutes':int(raw_early//60),'reported_early_minutes':int(reported//60),
      'included_early_minutes':int(early//60),'unresolved_early_minutes':int((max(raw_early,reported) if report else unclassified)//60) if unresolved else 0,
      'above_eight_hours_minutes':max(0,minutes-480),
      'payroll_review': 'Unresolved attendance - review before payroll' if long or unresolved else 'Open shift - provisional' if data['state']=='in' else 'Attendance ready for payroll review; pay rules not calculated'}
