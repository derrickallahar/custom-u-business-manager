 'use strict';
const el=id=>document.getElementById(id);
let page=1,sequence=0,controller,user=null,dashEpoch=0,dashController,historyLoaded=false;
const node=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
const money=c=>'BSD '+(c/100).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const can=k=>user?.me.role==='admin'||user?.me.permissions?.[k]===true;
async function request(url,signal){const r=await fetch(url,{credentials:'same-origin',cache:'no-store',signal});if(!r.ok){if(r.status===401||r.status===403)clearUser();throw Error(r.status===401||r.status===403?'Access denied. Sign in with your staff account.':'Information unavailable. Please try again.');}return r.json();}
async function load(){
 if(!user||user.me.role!=='admin'||!user.archive_configured)return;historyLoaded=true;
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
 user=null;dashEpoch++;sequence++;dashController?.abort();controller?.abort();historyLoaded=false;
 for(const id of ['overview','recent','quick-links','rows','detail','identity','dashboard-status','status'])el(id).replaceChildren();
 el('history-panel').hidden=true;el('history-panel').open=false;el('search').value='';el('kind').value='';el('positive').checked=false;
 el('viewer').hidden=true;el('login').hidden=false;el('login-status').textContent='Sign in to continue.';window.CustomUShell?.clear();
}
function showUser(result){
 user=result;el('login').hidden=true;el('viewer').hidden=false;el('identity').textContent=result.me.email;
 el('history-panel').hidden=result.me.role!=='admin'||!result.archive_configured;
 el('status').textContent=result.archive_configured?'':'No history archive has been imported yet.';
 window.CustomUShell?.setSession(result);overview();openHistory();
}
function openHistory(){if(location.hash==='#history'&&!el('history-panel').hidden){el('history-panel').open=true;el('history-panel').scrollIntoView?.({block:'start'});if(!historyLoaded)load();}}
window.addEventListener('hashchange',openHistory);
el('history-panel').addEventListener('toggle',()=>{if(el('history-panel').open&&!historyLoaded)load();});
async function overview(){
 const ticket=++dashEpoch;dashController?.abort();dashController=new AbortController();const signal=dashController.signal;
 el('overview').replaceChildren();el('recent').replaceChildren();el('quick-links').replaceChildren();el('dashboard-status').textContent='Loading overview…';
 if(!user?.crm_enabled){el('dashboard-status').textContent='Business tools are not enabled for this workspace.';return;}
 const areas=[['Customers','customers'],['Quotes','quotes'],['Invoices','invoices'],['Payments','payments'],['Production','jobs'],['Products & pricing','products']];
 for(const [label,key] of areas)if(can(key+'.view')){const a=node('a','cu-quick-link',label);a.href='/'+key;el('quick-links').append(a);}
 if(user.me.role==='admin'){const a=node('a','cu-quick-link','Statements');a.href='/statements';el('quick-links').append(a);}
 if(!el('quick-links').children.length)el('quick-links').append(node('p','cu-empty','Ask your administrator to assign access to your work areas.'));
 const tasks=[];
 function card(label,href,note,url,read,documents){
  const a=node('a','cu-metric');a.href=href;const value=node('strong','cu-metric-value','…');a.append(node('span','cu-metric-label',label),value,node('small','cu-metric-note',note));el('overview').append(a);
  tasks.push((async()=>{try{const data=await request(url,signal);if(ticket!==dashEpoch)return;value.textContent=read(data);if(documents)recentDocuments(data,documents);}catch(e){if(ticket!==dashEpoch||e.name==='AbortError')return;value.textContent='Unavailable';value.title=e.message;throw e;}})());
 }
 if(user.me.role==='admin')card('Amount owed','/statements','Live invoices and imported balances','/api/statements?mode=live&q=&status=all&page=1',r=>{if(!Number.isSafeInteger(r.totals?.balance_cents))throw Error('Invalid balance response');return money(r.totals.balance_cents);});
 const count=r=>{if(!Number.isSafeInteger(r.total)||r.total<0)throw Error('Invalid count response');return r.total.toLocaleString('en-US');};
 if(can('quotes.view'))card('Saved quotes','/quotes','All saved quotes, including drafts','/api/quotes?q=&page=1',count,'quotes');
 if(can('invoices.view'))card('Saved invoices','/invoices','Live and test documents, including drafts','/api/invoices?q=&page=1',count,'invoices');
 if(can('jobs.view'))card('Active production jobs','/jobs?mode=live','Live jobs in planning, production, ready or on hold','/api/jobs?mode=live&q=&status=&page=1',r=>{const stages=['planning','in_production','ready','on_hold'];if(!r.counts||stages.some(k=>!Number.isSafeInteger(r.counts[k]??0)||(r.counts[k]??0)<0))throw Error('Invalid job counts');return stages.reduce((n,k)=>n+(r.counts[k]??0),0).toLocaleString('en-US');});
 const results=await Promise.allSettled(tasks);if(ticket!==dashEpoch)return;
 const errors=results.some(r=>r.status==='rejected');el('dashboard-status').textContent=errors?'Some information could not be loaded. Use Refresh overview to try again.':'Overview refreshed.';
 if(!el('recent').children.length)el('recent').append(node('p','cu-empty',errors?'Documents could not be loaded. Open Quotes or Invoices to check.':'No documents to show for your available work areas.'));
}
function recentDocuments(result,kind){
 if(!Array.isArray(result.data))return;
 const section=node('section');section.append(node('h3','',kind==='quotes'?'Quotes':'Invoices'));const list=node('ul','cu-recent-list');
 for(const d of result.data.slice(0,3)){const li=node('li'),a=node('a','',d.number||'Open document');a.href='/'+kind+'/'+encodeURIComponent(d.id)+'/print';a.target='_blank';a.rel='noopener';a.title='Open saved document preview';li.append(a,node('small','',(d.customer||'')+' · '+(d.status==='issued'?'Finalised':d.status==='finalised'?'Finalised':'Draft')+(d.is_test?' · TEST':'')+' · '+money(d.total_cents)));list.append(li);}
 if(!list.children.length)section.append(node('p','cu-empty','No saved '+kind+'.'));else section.append(list);
 // Keep the order stable even when requests complete in a different order.
 section.dataset.kind=kind;el('recent').append(section);for(const n of [...el('recent').children].sort((a,b)=>a.dataset.kind==='quotes'?-1:b.dataset.kind==='quotes'?1:0))el('recent').append(n);
}
el('refresh-dashboard').onclick=async()=>{el('refresh-dashboard').disabled=true;try{const result=await request('/api/session');if(user)showUser(result);}catch(e){if(user)el('dashboard-status').textContent=e.message;}finally{el('refresh-dashboard').disabled=false;}};
el('login').onsubmit=async e=>{
 e.preventDefault();el('sign-in').disabled=true;el('login-status').textContent='Signing in…';
 try{const response=await fetch('/api/login',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:el('email').value,password:el('password').value,mobile:!!(navigator.userAgentData?.mobile||/Android|iPhone|iPad|iPod|Mobile|Tablet/i.test(navigator.userAgent)||navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1)})});if(!response.ok){let info={};try{info=await response.json();}catch{}const message={ADMIN_MOBILE_ONLY:'Mobile sign-in is available to administrators only. Use an approved work computer.',APPROVED_COMPUTER_REQUIRED:'This browser needs administrator approval. Ask your administrator to sign in here and approve this work computer under HR.',DEVICE_CHECK_UNAVAILABLE:'Computer approval could not be checked. Please try again.'}[info.error];throw Error(message||(response.status===429?'Please wait a minute before trying again.':'Sign-in failed or staff access is unavailable.'));}showUser(await response.json());}
 catch(e){el('login-status').textContent=e.message;}finally{el('password').value='';el('sign-in').disabled=false;}
};
el('logout').onclick=async()=>{clearUser();try{const response=await fetch('/api/logout',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:'{}'});if(!response.ok)throw Error();el('login-status').textContent='Signed out.';}catch(e){el('login-status').textContent='Sign-out could not be confirmed. Reconnect and use Sign out again.';}};
(async()=>{try{showUser(await request('/api/session'));}catch(e){clearUser();}})();
