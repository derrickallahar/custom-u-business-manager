/* Read-only ShopVox rows alongside working documents. No import or billing writes. */
(() => {
 'use strict';
 const get=id=>document.getElementById(id),node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
 let options=null,enabled=false,configured=false,epoch=0;
 function clear(){epoch++;enabled=false;configured=false;get('document-source-label').hidden=true;get('document-source').value='all';get('shopvox-status').textContent='';document.querySelectorAll('[data-shopvox]').forEach(n=>n.remove());}
 function source(){return enabled?get('document-source').value:'working';}
 function mount(o){options=o;get('document-source').addEventListener('change',()=>o.onChange());}
 function start(s){epoch++;enabled=s.me?.role==='admin';configured=s.archive_configured===true;get('document-source-label').hidden=!enabled;get('document-source').value=enabled?'all':'working';}
 async function append({q,page,total}){
  const mode=source(),ticket=epoch;const info=get('shopvox-status');info.textContent='';if(!enabled||mode==='working')return;
  if(!configured){info.textContent='The ShopVox history archive is not connected to this deployment. Existing Business Manager documents are still shown.';return;}
  info.textContent='Loading imported ShopVox '+options.kind+'s…';
  try{
   const response=await fetch('/api/history?'+new URLSearchParams({kind:options.kind,q,page:String(page),positive:'0'}),{credentials:'same-origin',cache:'no-store'});
   if(ticket!==epoch)return;
   if(response.status===401||response.status===403){options.onDenied();throw Object.assign(Error('Access ended. Return to the dashboard to sign in.'),{accessEnded:true});}
   let data;try{data=await response.json();}catch{throw Error('ShopVox records could not be read. Search again to retry.');}
   if(!response.ok||!Array.isArray(data.data)||!Number.isSafeInteger(data.total)||data.total<0)throw Error('ShopVox records could not be loaded. Search again to retry.');
   if(ticket!==epoch||!enabled)return;
   const rows=get('rows');for(const r of data.data){
    const tr=node('tr');tr.dataset.shopvox='true';
    const values=[`ShopVox ${r.number}`,r.customer,'Imported · '+(r.status||'No source status')];
    if(options.kind==='invoice')values.push('See imported details');
    values.push(r.total||'—');for(const value of values)tr.append(node('td',value));
    const td=node('td'),a=node('a','Open imported '+options.kind);a.href='/'+options.kind+'s/shopvox/'+encodeURIComponent(r.id);td.append(a);tr.append(td);rows.append(tr);
   }
   const native=mode==='all'?total:0,pages=Math.max(1,Math.ceil(native/50),Math.ceil(data.total/50));
   get('next').dataset.more=page*50<Math.max(native,data.total)?'1':'';
   get('count').textContent=(mode==='all'?total+' Business Manager · ':'')+data.total+' imported from ShopVox · Page '+page+' of '+pages;
   info.textContent=(mode==='all'?'Up to 50 documents from each source per page. ':'')+'ShopVox records retain their exported details and status. They are historical records; current imported invoice balances are in Imported balances.';
   if(!rows.children.length)info.textContent='No matching documents. Try the original ShopVox number or customer name.';
  }catch(error){if(error.accessEnded)throw error;if(ticket===epoch)info.textContent=error.message;}
 }
 window.CustomUShopVox={mount,start,append,clear,onlyArchive:()=>source()==='shopvox'};
})();
