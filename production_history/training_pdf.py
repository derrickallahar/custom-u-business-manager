"""Printable course guide and separate manager-only assessment key."""
from html import escape
from io import BytesIO
from math import ceil
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether
from branding import draw_logo
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pathlib import Path
import reportlab

FONT_DIR=Path(reportlab.__file__).parent/'fonts'
pdfmetrics.registerFont(TTFont('TrainingRegular',str(FONT_DIR/'Vera.ttf')))
pdfmetrics.registerFont(TTFont('TrainingBold',str(FONT_DIR/'VeraBd.ttf')))

RED=colors.HexColor('#b72030');INK=colors.HexColor('#20242a')

def guide_pdf(course, answer_key=False):
    out=BytesIO();styles={
        'title':ParagraphStyle('title',fontName='TrainingBold',fontSize=25,leading=30,textColor=INK,spaceAfter=16),
        'h1':ParagraphStyle('h1',fontName='TrainingBold',fontSize=16,leading=21,textColor=INK,spaceBefore=18,spaceAfter=9,keepWithNext=True),
        'h2':ParagraphStyle('h2',fontName='TrainingBold',fontSize=11,leading=16,textColor=INK,spaceBefore=10,spaceAfter=5,keepWithNext=True),
        'body':ParagraphStyle('body',fontName='TrainingRegular',fontSize=10.5,leading=15.5,textColor=INK,spaceAfter=9,allowWidows=0,allowOrphans=0),
        'meta':ParagraphStyle('meta',fontName='TrainingRegular',fontSize=9,leading=13,textColor=colors.HexColor('#596174'),spaceAfter=10),
        'option':ParagraphStyle('option',fontName='TrainingRegular',fontSize=10.5,leading=15,textColor=INK,leftIndent=12,spaceAfter=4)
    }
    def p(text,style='body'):return Paragraph(escape(str(text)).replace('→','<font name="Symbol">&#8594;</font>').replace('\n','<br/>'),styles[style])
    def page(canvas,doc):
        canvas.saveState();draw_logo(canvas,44,756,95)
        canvas.setFillColor(INK);canvas.setFont('TrainingRegular',8);canvas.drawRightString(568,741,'CUSTOM U  /  STAFF TRAINING')
        canvas.setStrokeColor(RED);canvas.setLineWidth(1);canvas.line(44,717,568,717)
        canvas.setFont('TrainingRegular',8);canvas.setFillColor(colors.HexColor('#596174'))
        canvas.drawString(44,30,'Edition '+str(course['edition'])+'  |  '+('Manager answer key' if answer_key else 'Business Manager training'))
        canvas.drawRightString(568,30,str(doc.page));canvas.restoreState()
    doc=SimpleDocTemplate(out,pagesize=letter,rightMargin=44,leftMargin=44,topMargin=92,bottomMargin=52,title=course['title']+(' - Answer key' if answer_key else ''),author='Custom U')
    story=[p('Training answer key' if answer_key else 'Custom U Business Manager training guide','title'),p(course['title']+' | Edition '+course['edition'],'meta')]
    qs=course['questions'];required=ceil(len(qs)*course['pass_percent']/100)
    if answer_key:
        story += [p('For HR managers and administrators. Keep this separate from the employee guide.'),p(f"Pass mark: {course['pass_percent']}%. At least {required} of {len(qs)} answers must be correct.")]
        for n,q in enumerate(qs,1):
            story.extend([p(f'{n}. '+q['prompt'],'h2'),p(chr(65+q['correct_index'])+'. '+q['options'][q['correct_index']]),p(q['explanation'],'meta')])
    else:
        story += [p(course['summary']),p(f"Allow approximately {course['estimated_minutes']} minutes. Pass mark: {course['pass_percent']}% ({required} of {len(qs)} correct).",'meta'),
          p('How to complete this course','h1'),p('In Business Manager, open HR & time clock, then Training. Read and mark every lesson, complete the final test and confirm you completed it yourself. Your account records the result and course edition. Reading this PDF alone does not record completion. Retakes are allowed.'),
          p('Course contents','h1')]
        for n,lesson in enumerate(course['lessons'],1):story.append(p(f'{n:02d}   '+lesson['title']))
        story.append(PageBreak())
        for n,lesson in enumerate(course['lessons'],1):
            story.append(p(f'{n:02d}  '+lesson['title'],'h1'))
            paragraphs=lesson['body'].split('\n\n')
            for i,paragraph in enumerate(paragraphs):
                if paragraph=='Requesting time off':
                    story.append(KeepTogether([p(paragraph,'h2')]+[p(value) for value in paragraphs[i+1:]]))
                    break
                story.append(p(paragraph))
        story += [PageBreak(),p('Final knowledge test','title'),p(f'Select one answer for each question. Pass mark: {course["pass_percent"]}%. Complete the online test to record completion. Use this printed test for study or a supervised discussion.'),p('Employee name _______________________    Date _______________________','meta')]
        for n,q in enumerate(qs,1):
            block=[p(f'{n}. '+q['prompt'],'h2')]
            block.extend(p(f'{chr(65+i)}.  '+opt,'option') for i,opt in enumerate(q['options']))
            block.append(Spacer(1,8));story.append(KeepTogether(block))
    doc.build(story,onFirstPage=page,onLaterPages=page);return out.getvalue()
