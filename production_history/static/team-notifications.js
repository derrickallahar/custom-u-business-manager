/* Minimal in-app counters and first-sign-in link. No private profile values are fetched. */
(() => {
'use strict';
let busy=false,epoch=0;
const workspace=()=>document.getElementById('workspace')||document.getElementById('viewer');
const emit=(name,detail)=>window.dispatchEvent(new CustomEvent(name,{detail}));
function clear(){emit('cu-team-clear');epoch++;document.getElementById('cu-team-notice')?.remove();}
async function refresh(){const area=workspace();if(!area||area.hidden||document.hidden||busy){if(!area||area.hidden)clear();return;}const ticket=epoch,controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),15000);busy=true;
 try{const r=await fetch('/api/team?op=status',{signal:controller.signal,credentials:'same-origin',cache:'no-store'});if(ticket!==epoch||area.hidden)return;if(!r.ok){if(r.status===401||r.status===403)clear();else emit('cu-team-offline');return;}const d=await r.json();if(ticket!==epoch||area.hidden)return;emit('cu-team-status',d);let box=document.getElementById('cu-team-notice');if(!box){box=document.createElement('aside');box.id='cu-team-notice';box.className='cu-team-notice';box.setAttribute('aria-label','Team notifications');area.prepend(box);}box.replaceChildren();
 const a=document.createElement('a');a.href='/team#messages';a.textContent=d.unread_messages?`Team messages · ${d.unread_messages} unread`:'Team hub';a.addEventListener('click',e=>{if(document.getElementById('cu-live-chat')){e.preventDefault();emit('cu-chat-open');}});box.append(a);
 if(d.bulletins_due){const b=document.createElement('a');b.href='/team#board';b.textContent=`Bulletin board · ${d.bulletins_due} to acknowledge`;box.append(b);}
 if(d.onboarding_required&&location.pathname!=='/team'){const b=document.createElement('a');b.href='/team#setup';b.textContent='First sign-in: enter your employee identification details';box.append(b);}
 }catch{emit('cu-team-offline');}finally{clearTimeout(timeout);busy=false;}}
window.addEventListener('cu-team-clear',()=>{epoch++;document.getElementById('cu-team-notice')?.remove();});
function boot(){const area=workspace();if(area)new MutationObserver(()=>{if(area.hidden)clear();else refresh();}).observe(area,{attributes:true,attributeFilter:['hidden']});refresh();setInterval(refresh,8000);document.addEventListener('visibilitychange',refresh);window.addEventListener('cu-chat-read',refresh);window.addEventListener('cu-chat-sent',refresh);}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
