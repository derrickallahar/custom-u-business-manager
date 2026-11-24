/* Multiple finishes share a reviewed set of independently positioned surfaces. */
(function(){'use strict';
 const finishNames={colour:'Colour / UV printing','engraved-dark':'Engraving — dark','engraved-light':'Engraving — light'};
 const placementNames={centre:'Centre','left-chest':'Left chest',back:'Back','left-sleeve':'Left sleeve','right-sleeve':'Right sleeve','bottom-right':'Bottom right','upper-left':'Upper left',front:'Front'};
 const families={generic:['centre'],shirt:['left-chest','centre','back','left-sleeve','right-sleeve'],journal:['centre','bottom-right','upper-left'],drinkware:['centre','front']};
 window.CustomUMockupOptions={mount(h){
  const e=id=>document.getElementById(id),clone=x=>JSON.parse(JSON.stringify(x));
  let context='',selected=[],views=new Map(),jobs=[],started=false,completed=false,urls=[];
  const label=k=>k==='centre'&&h.state().family==='shirt'?'Centre chest':placementNames[k];
  const finishes=()=>[...e('branding-finishes').querySelectorAll('input:checked')].map(x=>x.value);
  function note(s){e('branding-note').textContent=s;}
  function revoke(){for(const u of urls)URL.revokeObjectURL(u);urls=[];}
  function invalidate(){if(started)return;revoke();jobs=[];completed=false;e('branding-results').replaceChildren();e('branding-open').hidden=true;}
  function image(record,alt){const bytes=Uint8Array.from(atob(record.content_base64),c=>c.charCodeAt(0)),url=URL.createObjectURL(new Blob([bytes],{type:'image/webp'}));urls.push(url);const img=document.createElement('img');img.src=url;img.alt=alt;return img;}
  function clear(){revoke();context='';selected=[];views.clear();jobs=[];started=false;completed=false;e('branding-views').replaceChildren();e('branding-results').replaceChildren();e('branding-open').hidden=true;e('branding-open').removeAttribute('href');note('');}
  function choices(){e('branding-placement-choices').replaceChildren();for(const k of families[h.state().family]||families.generic){const lab=document.createElement('label');lab.className='option-check';const input=document.createElement('input');input.type='checkbox';input.value=k;input.checked=selected.includes(k);input.onchange=()=>{if(started)return;if(input.checked&&selected.length===4){input.checked=false;note('Choose up to four placements per option.');return;}selected=[...e('branding-placement-choices').querySelectorAll('input:checked')].map(x=>x.value);invalidate();h.dirty();renderViews();controls();};lab.append(input,document.createTextNode(label(k)));e('branding-placement-choices').append(lab);}e('shirt-combinations').hidden=h.state().family!=='shirt';}
  function renderViews(){e('branding-views').replaceChildren();for(const k of selected){const card=document.createElement('article');card.className='branding-view';const title=document.createElement('h3');title.textContent=label(k);const state=document.createElement('p'),view=views.get(k);state.textContent=view?'Preview captured · '+(view.config.scale?view.config.scale.print_width+' in wide':'manual placement'):'Set up and capture a preview for this surface.';const setup=document.createElement('button');setup.type='button';setup.textContent='Set up '+label(k);setup.onclick=()=>{if(!h.state().busy&&!started)h.configure(k);};const capture=document.createElement('button');capture.type='button';capture.textContent='Use this preview';capture.dataset.capture=k;capture.onclick=()=>{const s=h.state();if(started||s.busy||!s.preview||s.preview.config.placement!==k)return;views.set(k,{image_id:e('source-image').value,...clone(s.preview)});invalidate();h.dirty();renderViews();controls();note(label(k)+' captured. Set up any remaining surfaces, then generate the selected finishes.');};card.append(title,state,setup,capture);if(view){const img=document.createElement('img');img.src='data:image/webp;base64,'+view.preview.content_base64;img.alt=label(k)+' captured preview';card.append(img);}e('branding-views').append(card);}}
  function controls(){const s=h.state(),next=[s.customer?.id||'',s.product?.id||'',s.family].join(':');if(next!==context){const discarded=context&&views.size;clear();context=next;selected=[s.family==='shirt'?'left-chest':'centre'];choices();renderViews();if(discarded)note('Customer, product or product type changed. Set up a new option set.');}
   const edit=h.canEdit(),ready=edit&&s.customer&&s.product&&!s.busy&&!s.photoPending;
   for(const x of e('branding-options').querySelectorAll('input,button'))x.disabled=!ready||started;
   for(const b of e('branding-views').querySelectorAll('[data-capture]'))b.disabled=!ready||started||!s.preview||s.preview.config.placement!==b.dataset.capture;
   e('branding-generate').disabled=!ready||started||!finishes().length||!selected.length||selected.some(k=>!views.has(k));
   e('branding-save').disabled=!ready||!jobs.length||completed;
   e('branding-save').textContent=started&&!completed?'Resume saving options & create catalogue':'Save options & create catalogue';
   e('branding-reset').disabled=s.busy||!edit;
  }
  function combine(keys){if(started)return;selected=keys;invalidate();choices();renderViews();controls();h.dirty();}
  e('combo-left-back').onclick=()=>combine(['left-chest','back']);e('combo-centre-back').onclick=()=>combine(['centre','back']);
  e('branding-finishes').onchange=()=>{invalidate();h.dirty();controls();};
  e('branding-reset').onclick=()=>{if(started&&!confirm('Clear this option set? Already saved mockups will remain in Saved mockups.'))return;clear();controls();};
  e('branding-generate').onclick=()=>h.run(async()=>{
   if(started)return;const s=h.state();if(!s.customer||!s.product||!selected.length||!finishes().length||selected.some(k=>!views.has(k)))throw Error('Capture a preview for each selected placement first.');
   invalidate();const pending=[];const keys=[...selected],chosen=finishes();
   for(const finish of chosen)for(const k of keys){const view=views.get(k);note('Generating '+finishNames[finish]+' · '+label(k)+'…');const r=await h.api('/api/mockups/preview',{product_id:s.product.id,image_id:view.image_id,logo:view.logo,config:{...view.config,finish}});if(!r.preview?.sha256||!r.preview?.content_base64||r.source_sha256!==view.source_sha256)throw Error('A source photo changed. Capture its preview again before generating options.');pending.push({id:crypto.randomUUID(),customer_id:s.customer.id,product_id:s.product.id,image_id:view.image_id,title:Array.from(s.product.data.name+' — '+finishNames[finish]+' — '+label(k)).slice(0,160).join(''),...r,saved:false});}
   jobs=pending;for(const job of jobs){const card=document.createElement('article');card.className='branding-view';const title=document.createElement('h3');title.textContent=finishNames[job.config.finish]+' · '+label(job.config.placement);card.append(title,image(job.preview,title.textContent));e('branding-results').append(card);}h.dirty();note(chosen.length+' option(s) generated with '+keys.length+' view(s) each. Review below, then save and create the catalogue.');
  });
  e('branding-save').onclick=()=>h.run(async()=>{
   if(!jobs.length||completed)return;started=true;
   try{for(const job of jobs){if(job.saved)continue;note('Saving '+(jobs.filter(x=>x.saved).length+1)+' of '+jobs.length+' mockups…');const {id,product_id,image_id,customer_id,title,logo,config,source_sha256}=job;const r=await h.api('/api/mockups/save',{id,product_id,image_id,customer_id,title,logo,config,source_sha256});if(r.data?.id!==id||r.data?.preview?.sha256!==job.preview.sha256)throw Error('Save not confirmed. Use Resume saving to keep the same save IDs.');job.saved=true;}}catch(error){if(h.canEdit())note('Saving paused. Use Resume saving options to continue; confirmed saves and their IDs are kept.');throw error;}
   const groups=[...new Set(jobs.map(j=>j.config.finish))].map(f=>jobs.filter(j=>j.config.finish===f).map(j=>j.id).join(','));
   const url='/catalogues/new?mockups='+encodeURIComponent(groups.join(';'));completed=true;e('branding-open').href=url;e('branding-open').hidden=false;e('branding-open').onclick=ev=>{ev.preventDefault();h.navigate(url);};note('All selected mockups saved. Opening the catalogue draft…');h.navigate(url);
  });
  return {controls,clear};
 }};
})();
