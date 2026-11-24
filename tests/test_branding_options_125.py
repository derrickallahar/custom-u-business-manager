"""Run with PYTHONPATH=production_history python -m unittest discover -s tests."""
import copy, io, unittest
from PIL import Image
from pypdf import PdfReader
from product_images import encode_image
from mockup_render import render, configuration
from catalogue_data import items_valid, snapshot_assets
from catalogue_pdf import render_catalogue

def uid(n):return f'12500000-0000-4000-8000-{n:012d}'
def fixture():
    out=io.BytesIO();Image.new('RGBA',(300,400),'white').save(out,format='PNG');base=encode_image(out.getvalue())
    out=io.BytesIO();Image.new('RGBA',(100,40),'red').save(out,format='PNG');logo=encode_image(out.getvalue())
    config=dict(family='shirt',placement='left-chest',finish='colour',x=63,y=32,width=12,rotation=0)
    previews=[render(base,logo,config),render(base,logo,{**config,'placement':'back','width':30})]
    views=[dict(visual_kind='mockup',visual_id=uid(i+10),visual_sha256=p['sha256'],label=label) for i,(p,label) in enumerate(zip(previews,['Left chest','Back']))]
    item=dict(product_id=uid(2),product_code='PRIVATE-CODE',name='Shirt',description='Two views of one shirt option',unit='Each',unit_price='25.00',vat_rate='10.00',finish='UV printing',placement='Left chest + back',**{k:views[0][k] for k in ('visual_kind','visual_id','visual_sha256')},views=views)
    doc=dict(customer_id=uid(1),customer_name='Test client',title='Branding choices',intro='',items=[item])
    assets={'mockup:'+v['visual_id']:p for v,p in zip(views,previews)}
    return doc,assets,config,base,logo

class BrandingOptions(unittest.TestCase):
    def test_combined_pdf_has_one_option_price_and_both_views(self):
        doc,assets,*_=fixture();raw=render_catalogue(doc,assets);self.assertEqual(raw,render_catalogue(doc,assets))
        pdf=PdfReader(io.BytesIO(raw));self.assertEqual(len(pdf.pages),2);text=pdf.pages[1].extract_text()
        for label in ('Left chest','Back','BSD 25.00','BSD 27.50'):self.assertIn(label,text)
        self.assertNotIn('PRIVATE-CODE',text);self.assertEqual(len(pdf.pages[1].images),3) # two views + logo
    def test_old_single_view_and_new_sleeves(self):
        doc,assets,c,b,l=fixture();del doc['items'][0]['views'];render_catalogue(doc,{next(iter(assets)):next(iter(assets.values()))})
        for placement in ('left-sleeve','right-sleeve'):
            self.assertEqual(configuration({**c,'placement':placement})['placement'],placement);render(b,l,{**c,'placement':placement})
        with self.assertRaises(ValueError):configuration({**c,'family':'journal','placement':'left-sleeve'})
    def test_invalid_group_and_total_view_limits(self):
        doc,*_=fixture();item=doc['items'][0]
        for value in ([],None,[item['views'][1]],item['views']*2,[{**item['views'][0],'product_id':uid(8)}],[{**item['views'][0],'label':''}]):
            bad=copy.deepcopy(item);bad['views']=value
            with self.subTest(value=value),self.assertRaises(ValueError):items_valid([bad])
        with self.assertRaises(ValueError):items_valid([item]*7)
        items_valid([item]*6)
    def test_backup_checks_every_view_customer_product_and_hash(self):
        doc,assets,*_=fixture();obj={'products':[{'id':uid(2)}],'product_images':[],'crm':{'records':[{'id':uid(1),'kind':'customer'}]},'mockups':[{'id':v['visual_id'],'product_id':uid(2),'customer_id':uid(1),'preview':assets['mockup:'+v['visual_id']]} for v in doc['items'][0]['views']]}
        self.assertEqual(snapshot_assets(doc,obj),assets)
        for field in ('customer_id','product_id'):
            bad=copy.deepcopy(obj);bad['mockups'][1][field]=uid(99)
            with self.assertRaises(ValueError):snapshot_assets(doc,bad)
        bad=copy.deepcopy(doc);bad['items'][0]['views'][1]['visual_sha256']='0'*64
        with self.assertRaises(ValueError):snapshot_assets(bad,obj)
