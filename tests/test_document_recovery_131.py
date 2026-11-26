import copy,json,unittest
from pathlib import Path
from recover_workspace import validate_100
F=json.loads(Path('/tmp/documents131_cases.json').read_text())
def snapshot():
    s=copy.deepcopy(F['snapshot']);records=s.pop('crmRecords');profile=s.pop('profileRecord');exported='2026-12-31T00:00:00+00:00'
    crm={'format':'custom-u-crm-snapshot-094','schema_release':'093','source_project':'ldzugsrflgrlxmntbqtc','exported_at':exported,'records':records,'audit':[{'id':n+1,'record_id':r['id'],'actor_id':F['admin'],'happened_at':r['updated_at'],'before_record':None,'after_record':r} for n,r in enumerate(records)]}
    return {**s,'profile':profile,'crm':crm,'format':'custom-u-workspace-snapshot-100','source_project':'ldzugsrflgrlxmntbqtc','exported_at':exported}
class Recovery(unittest.TestCase):
    def test_full_replay_retains_draft_source_and_earlier_revisions(self):
        validate_100(snapshot())
    def test_original_source_and_history_cannot_be_rewritten(self):
        s=snapshot();i=next(i for i in s['invoices'] if 'original_quote_data' in i['quote_snapshot']);i['quote_snapshot']['original_quote_data']['title']='Changed history'
        with self.assertRaises(ValueError):validate_100(s)
        s=snapshot();s['invoice_audit']=[a for a in s['invoice_audit'] if a['after_record']['version']!=2]
        with self.assertRaises(ValueError):validate_100(s)
if __name__=='__main__':unittest.main()
