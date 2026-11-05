"""Explicit staff capabilities; SQL independently enforces the same restrictions."""
KEYS=('customers.view','customers.create','customers.edit','quotes.view','quotes.create','quotes.edit','quotes.approve','invoices.view','invoices.create','invoices.edit','invoices.issue','payments.view','payments.record','payments.reverse')

def can(me,key):
    return isinstance(me,dict) and (me.get('role')=='admin' or isinstance(me.get('permissions'),dict) and me['permissions'].get(key) is True)

def allowed(me,area,payload=None):
    if me.get('role')=='admin':return True
    if not can(me,area+'.view'):return False
    if payload is None:return True
    op=payload.get('op')
    if area=='customers':
        return op in ('list','get') or op in ('save_customer','save_contact') and (can(me,'customers.create') or can(me,'customers.edit'))
    if area=='quotes':
        return op in ('list','get','profile') or op=='issue' and can(me,'quotes.approve') or op=='save' and can(me,'customers.view') and (can(me,'quotes.create') or can(me,'quotes.edit'))
    if area=='invoices':
        return op in ('list','get') or op=='create' and can(me,'invoices.create') and can(me,'quotes.view') or op=='save' and can(me,'invoices.edit') or op=='issue' and can(me,'invoices.issue')
    if area=='payments':
        return can(me,'invoices.view') and (op in ('list','invoice','receipt') or op=='record' and can(me,'payments.record') or op=='reverse' and can(me,'payments.reverse'))
    return False
