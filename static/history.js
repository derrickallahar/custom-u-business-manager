'use strict';
const el=id=>document.getElementById(id);
let page=1,sequence=0,controller;
async function request(url,signal){const r=await fetch(url,{credentials:'same-origin',cache:'no-store',signal});if(!r.ok)throw Error(r.status===401||r.status===403?'Access denied. Sign in as an administrator.':'History unavailable. Please try again.');return r.json();}
async function load(){
 const ticket=++sequence;if(controller)controller.abort();controller=new AbortController();
 el('rows').replaceChildren();el('detail').replaceChildren();el('prev').disabled=true;el('next').disabled=true;el('status').textContent='Loading…';
 try{
 const p=new URLSearchParams({q:el('search').value,kind:el('kind').value,positive:el('positive').checked?'1':'0',page:String(page)});
 const result=await request('/api/history?'+p,controller.signal);if(ticket!==sequence)return;
 el('status').textContent=result.total+' fictional records · Page '+page+' of '+Math.max(1,Math.ceil(result.total/50));
 el('prev').disabled=page===1;el('next').disabled=page*50>=result.total;
 for(const r of result.data){
 const tr=document.createElement('tr');
 for(const k of ['kind','number','customer','total','balance']){const td=document.createElement('td');td.textContent=r[k];tr.append(td);}
 const td=document.createElement('td'),button=document.createElement('button');button.textContent='View';
 button.onclick=async()=>{el('detail').replaceChildren();try{
 const detail=await request('/api/history/records/'+encodeURIComponent(r.id),controller.signal);
 if(ticket!==sequence)return;
 const pre=document.createElement('div');pre.textContent=Object.entries(detail.data).filter(([k])=>!['id','attachments'].includes(k)).map(([k,v])=>k+': '+v).join('\n');el('detail').append(pre);
 for(const f of detail.data.attachments){const a=document.createElement('a');a.href=f.url;a.textContent='Download '+f.name;a.style.display='block';el('detail').append(a);}
 el('detail').focus();
 }catch(e){if(e.name!=='AbortError'){el('rows').replaceChildren();el('detail').replaceChildren();el('status').textContent=e.message;}}};
 td.append(button);tr.append(td);el('rows').append(tr);
 }
 }catch(e){if(e.name!=='AbortError'&&ticket===sequence)el('status').textContent=e.message;}
}
el('filter').onsubmit=e=>{e.preventDefault();page=1;load();};
el('prev').onclick=()=>{page--;load();};
el('next').onclick=()=>{page++;load();};
load();
