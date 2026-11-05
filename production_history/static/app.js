'use strict';
const el=id=>document.getElementById(id);
let page=1,sequence=0,controller;
async function request(url,signal){const r=await fetch(url,{credentials:'same-origin',cache:'no-store',signal});if(!r.ok){if(r.status===401||r.status===403)clearUser();throw Error(r.status===401||r.status===403?'Access denied. Sign in as an administrator.':'History unavailable. Please try again.');}return r.json();}
async function load(){
 const ticket=++sequence;if(controller)controller.abort();controller=new AbortController();
 el('rows').replaceChildren();el('detail').replaceChildren();el('prev').disabled=true;el('next').disabled=true;el('status').textContent='Loading…';
 try{
 const p=new URLSearchParams({q:el('search').value,kind:el('kind').value,positive:el('positive').checked?'1':'0',page:String(page)});
 const result=await request('/api/history?'+p,controller.signal);if(ticket!==sequence)return;
 el('status').textContent=result.total+' historical records · Page '+page+' of '+Math.max(1,Math.ceil(result.total/50));
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

function clearUser(){
 el('quotes-link').hidden=true;el('invoices-link').hidden=true;
 sequence++;if(controller)controller.abort();el('rows').replaceChildren();el('detail').replaceChildren();
 el('viewer').hidden=true;el('login').hidden=false;el('identity').textContent='';el('login-status').textContent='Sign in to continue.';
}
function showUser(result){
 el('customers-link').hidden=!result.crm_enabled;
 el('quotes-link').hidden=!result.crm_enabled;el('invoices-link').hidden=!result.crm_enabled;
 el('login').hidden=true;el('viewer').hidden=false;el('identity').textContent=result.me.email;
 el('filter').hidden=!result.archive_configured;el('pages').hidden=!result.archive_configured;
 if(result.archive_configured){page=1;load();}
 else{el('status').textContent='Your administrator login is connected. No history archive has been imported yet.';}
}
el('login').onsubmit=async e=>{
 e.preventDefault();el('sign-in').disabled=true;el('login-status').textContent='Signing in…';
 try{
 const response=await fetch('/api/login',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:el('email').value,password:el('password').value})});
 if(!response.ok)throw Error(response.status===429?'Please wait a minute before trying again.':'Sign-in failed or administrator access is unavailable.');
 showUser(await response.json());
 }catch(e){el('login-status').textContent=e.message;}finally{el('password').value='';el('sign-in').disabled=false;}
};
el('logout').onclick=async()=>{
 clearUser();
 try{const response=await fetch('/api/logout',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:'{}'});if(!response.ok)throw Error();el('login-status').textContent='Signed out.';}
 catch(e){el('login-status').textContent='Sign-out could not be confirmed. Reconnect and use Sign out again.';}
};
(async()=>{try{showUser(await request('/api/session'));}catch(e){clearUser();}})();
