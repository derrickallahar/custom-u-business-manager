import {JSDOM} from 'jsdom';
import utils from 'jsdom/lib/generated/idl/utils.js';
import fs from 'node:fs';import assert from 'node:assert/strict';
const uid=n=>'12500000-0000-4000-8000-'+String(n).padStart(12,'0');
const customer={id:uid(1),active:true,data:{name:'Test client'}},product={id:uid(2),active:true,data:{code:'PRIVATE',name:'Shirt',description:'Test shirt',unit:'Each',unit_price:'12.00',vat_rate:'10.00'}};
let rows=new Map(),saves=[],previews=[],failed=false,failSave=true,nav='',revoked=false;
const image={content_base64:'AQ==',width:500,height:600,sha256:'a'.repeat(64)};
const fetcher=async(path,opts={})=>{
 let data;
 if(path==='/api/session')data={me:{role:'office',email:'test@example.invalid',permissions:{'products.view':true,'customers.view':true,'products.edit':!revoked}}};
 else if(path==='/api/customers/'+customer.id)data={data:customer};
 else if(path.startsWith('/api/customers'))data={data:[customer],total:1};
 else if(path.endsWith('/images'))data={data:[{id:uid(3),active:true,caption:'Front'},{id:uid(4),active:true,caption:'Back'}]};
 else if(path==='/api/products/'+product.id)data={data:product};
 else if(path.startsWith('/api/products'))data={data:[product],total:1};
 else if(path==='/api/mockups/preview'){const p=JSON.parse(opts.body);previews.push(p);data={preview:image,logo:image,config:p.config,source_sha256:'b'.repeat(64)};}
 else if(path==='/api/mockups/save'){const p=JSON.parse(opts.body);saves.push(p);rows.set(p.id,{...p,preview:image,active:true,product_name:product.data.name});if(failSave&&!failed&&saves.length===2){failed=true;throw new TypeError('Lost response');}data={data:rows.get(p.id)};}
 else if(path.startsWith('/api/mockups/'))data={data:rows.get(path.split('/').pop())};
 else if(path==='/api/catalogues/preview'){previews.push(JSON.parse(opts.body));return {ok:true,status:200,headers:{get:()=> 'application/pdf'},blob:async()=>new Blob(['pdf'])};}
 else data={data:[...rows.values()],total:rows.size};
 return {ok:true,status:200,json:async()=>JSON.parse(JSON.stringify(data))};
};
function page(name,url){const d=new JSDOM(fs.readFileSync('production_history/static/'+name+'.html','utf8'),{url:'https://fixture.invalid'+url,runScripts:'outside-only'}),w=d.window;w.confirm=()=>true;w.URL.createObjectURL=()=> 'blob:preview';w.URL.revokeObjectURL=()=>{};w.fetch=fetcher;utils.implForWrapper(w.location)._locationObjectNavigate=t=>{nav=t.path.join('/')+(t.query?'?'+t.query:'');};return d;}
const tick=()=>new Promise(r=>setTimeout(r,5));async function settle(w){for(let n=0;n<200;n++){await tick();if(!w.document.getElementById('refresh').disabled)return;}throw Error('UI busy');}
const d=page('mockups','/mockups/new'),w=d.window,e=id=>w.document.getElementById(id);
w.eval(fs.readFileSync('production_history/static/mockup-options.js','utf8'));w.eval(fs.readFileSync('production_history/static/mockups.js','utf8'));await settle(w);
e('find-customer').click();await settle(w);e('customer-results').firstChild.click();e('find-product').click();await settle(w);e('product-results').firstChild.click();await settle(w);
e('family').value='shirt';e('family').dispatchEvent(new w.Event('change'));e('combo-left-back').click();
Object.defineProperty(e('logo'),'files',{configurable:true,value:[new w.File(['fake'],'test.png',{type:'image/png'})]});
for(const [placement,photo] of [['left-chest',3],['back',4]]){
 const card=[...e('branding-views').children].find(c=>c.querySelector('[data-capture]').dataset.capture===placement);card.querySelector('button').click();
 if(placement==='back')assert.equal(e('source-image').value,'');
 e('source-image').value=uid(photo);e('source-image').dispatchEvent(new w.Event('change'));
 e('preview').click();await settle(w);e('branding-views').querySelector(`[data-capture="${placement}"]`).click();
}
const engraving=e('branding-finishes').querySelector('[value="engraved-dark"]');engraving.checked=true;engraving.dispatchEvent(new w.Event('change',{bubbles:true}));
assert.equal(e('branding-generate').disabled,false);e('branding-generate').click();await settle(w);assert.equal(e('branding-results').children.length,4);assert.equal(rows.size,0);
e('branding-save').click();await settle(w);assert.equal(rows.size,2);assert.match(e('branding-save').textContent,/Resume/);assert.equal(e('branding-generate').disabled,true);
failSave=false;e('branding-save').click();await settle(w);assert.equal(rows.size,4);assert.equal(saves[1].id,saves[2].id);assert.equal(new Set(saves.map(x=>x.id)).size,4);assert.match(nav,/catalogues\/new\?mockups=/);
const generated=[...rows.values()];assert.equal(generated[0].image_id,uid(3));assert.equal(generated[1].image_id,uid(4));
const cat=page('catalogues','/'+nav),cw=cat.window,ce=id=>cw.document.getElementById(id);cw.eval(fs.readFileSync('production_history/static/catalogues.js','utf8'));await settle(cw);
assert.equal(ce('items').children.length,2);assert.equal(ce('items').querySelectorAll('figure').length,4);assert.equal(ce('items').querySelector('[data-field="unit_price"]').value,'');
ce('preview').click();await settle(cw);assert.match(ce('status').textContent,/valid price/);
for(const input of ce('items').querySelectorAll('[data-field="unit_price"]')){input.value='25.00';input.dispatchEvent(new cw.Event('input'));}
ce('preview').click();await settle(cw);const body=previews.at(-1);assert.equal(body.items.length,2);assert.equal(body.items[0].views.length,2);assert.equal(body.items[0].placement,'Left chest + Back');assert.equal(body.items[1].finish,'Engraving — dark');
revoked=true;e('refresh').click();await settle(w);assert.equal(e('branding-results').children.length,0);assert.equal(e('editor').hidden,true);
w.close();cw.close();console.log('Branding UI PASS: paired surfaces, independent photos, multiple finishes, preview-first, retry IDs, grouped catalogue handoff, reviewed pricing, permission clearing.');
