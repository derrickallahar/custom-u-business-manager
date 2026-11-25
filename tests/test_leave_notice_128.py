import copy,io,json,unittest
from pathlib import Path
from pypdf import PdfReader
from training_pdf import guide_pdf
from training_rules import validate_course
from hr_rules import check_record

class LeaveNotice(unittest.TestCase):
    def test_backup_records_and_new_start_time(self):
        records=json.loads(Path('/tmp/leave128_records.json').read_text())['hr_records']
        for row in records:check_record(row)
        personal=next(r for r in records if r['kind']=='leave' and 'start_time' in r['data'])
        for time in ['25:00','9:00',None,900]:
            bad=copy.deepcopy(personal);bad['data']['start_time']=time
            with self.assertRaises(ValueError):check_record(bad)
        old=copy.deepcopy(personal);old['data'].pop('start_time');check_record(old)

    def test_current_guide_and_assessment(self):
        course=json.loads(Path('production_history/training_starter_128.json').read_text());validate_course(course)
        self.assertEqual(course['edition'],'2');self.assertEqual(len(course['questions']),20)
        lesson=course['lessons'][7]['body'];self.assertNotIn('overtime',lesson.lower())
        for phrase in ['24 hours before it starts','14 calendar days before the first day of vacation','Submitting a request does not mean it has been approved','notify your manager as soon as you can','do not override leave entitlements under the law']:
            self.assertIn(phrase,lesson)
        self.assertIn('24 hours',course['questions'][17]['options'][course['questions'][17]['correct_index']])
        self.assertIn('14 calendar days',course['questions'][17]['options'][course['questions'][17]['correct_index']])
        self.assertIn('Notify your manager',course['questions'][16]['options'][course['questions'][16]['correct_index']])
        pdf=PdfReader(io.BytesIO(guide_pdf(course)));text=' '.join(' '.join(p.extract_text() for p in pdf.pages).split())
        self.assertIn('14 calendar days before the first day of vacation',text);self.assertIn('24 hours before it starts',text);self.assertNotIn('Overtime is recorded',text)
        self.assertIn('Edition 2',text)
        for page in pdf.pages:self.assertTrue(page.images)

if __name__=='__main__':unittest.main()
