/* Dedicated creation pages reuse each feature's existing authenticated editor. */
(() => {
'use strict';
const match=location.pathname.match(/^\/(quotes|invoices|mockups|catalogues|jobs|customers)\/new$/);if(!match)return;
const type=match[1],labels={quotes:'quote',invoices:'invoice',mockups:'mockup',catalogues:'catalogue',jobs:'job',customers:'customer'};
document.body.classList.add('cu-new-page');document.body.dataset.newKind=type;document.title='Custom U · New '+labels[type];
const hide=e=>{if(e){e.dataset.creationList='true';e.style.display='none';}};
for(const id of ['rows','saved','board'])hide(document.getElementById(id)?.closest('.card'));
if(type==='jobs'){
 const filters=document.getElementById('filters'),mode=document.getElementById('mode');
 if(mode){const wrap=document.createElement('div');wrap.className='card';const label=mode.closest('label');wrap.append(label);document.getElementById('sources-card').before(wrap);}
 hide(filters);for(const id of ['counts','page-info','prev','next','refresh'])hide(document.getElementById(id));
}
if(type==='customers'){const list=document.getElementById('rows')?.closest('section'),form=document.getElementById('customer-form');if(list)hide(list);const grid=form?.closest('.grid');if(grid)grid.style.gridTemplateColumns='1fr';}
for(const id of ['new','new-invoice','new-customer','new-job','refresh','show-backup','show-profile'])hide(document.getElementById(id));
const workspace=document.getElementById('workspace'),back=document.createElement('a');back.className='cu-creation-back';back.textContent='← Back to '+type;back.href='/'+type;
if(type==='jobs'&&new URLSearchParams(location.search).get('mode')==='live')back.href+='?mode=live';
workspace?.prepend(back);
const heading=document.querySelector('main > header h1,main > h1');if(heading)heading.textContent='New '+labels[type];
})();
