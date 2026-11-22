/* Persistent, session-gated chat UI. Message content and drafts stay in memory only. */
(() => {
'use strict';
const PREF='cu-chat-view-1161';
const make=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const button=(text,fn)=>{const b=make('button',text);b.type='button';b.addEventListener('click',fn);return b;};
const area=()=>document.getElementById('workspace')||document.getElementById('viewer');
let user='',root,launcher,panel,roster,conversation,log,composer,sendButton,notice,retry,older,back,title,badge,search;
let opened=false,peer='',people=[],rows=[],pending=null,sending=false,loading=false,polling=false,epoch=0,threadEpoch=0,hasMore=false;
let directoryAt=0,directoryBusy=false,lastPeople='',timer;
const drafts=new Map(),seen=new Map(),reading=new Set();
const active=()=>!!user&&area()&&!area().hidden;
const visible=()=>active()&&opened&&!document.hidden;
const atBottom=()=>log&&log.scrollHeight-log.scrollTop-log.clientHeight<80;
const display=id=>people.find(p=>p.id===id)?.email||'Team member';
const errors={RECIPIENT_UNAVAILABLE:'This team member no longer has active access.',MESSAGE_RATE_LIMIT:'Please wait a minute before sending more messages.',TEAM_STORAGE_LIMIT:'Message storage is full. Contact your administrator.',REQUEST_CONFLICT:'This message retry could not be matched. Contact your administrator.'};
function saveView(){if(!user)return;try{sessionStorage.setItem(PREF,JSON.stringify({user,open:opened,peer}));}catch{}}
function clear(){epoch++;threadEpoch++;user=peer='';people=[];rows=[];pending=null;sending=loading=polling=directoryBusy=false;directoryAt=0;lastPeople='';drafts.clear();seen.clear();reading.clear();root?.remove();root=null;clearTimeout(timer);try{sessionStorage.removeItem(PREF);}catch{}}
function status(text,error=false){if(!notice)return;notice.textContent=text;notice.dataset.error=String(error);}
async function request(payload,write=false){
 const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),15000);let r;
 try{
  try{r=await fetch(write?'/api/team/action':'/api/team?'+new URLSearchParams(payload),{method:write?'POST':'GET',credentials:'same-origin',cache:'no-store',signal:controller.signal,headers:write?{'Content-Type':'application/json'}:undefined,body:write?JSON.stringify(payload):undefined});}
  catch{throw Object.assign(Error(write?'Delivery is not confirmed. Use Retry send to check safely.':'Connection interrupted. Reconnecting automatically…'),{uncertain:write});}
  if(r.status===401||r.status===403){window.dispatchEvent(new CustomEvent('cu-team-clear'));throw Error('Sign in again from an approved computer.');}
  let d;try{d=await r.json();}catch{throw Object.assign(Error(write?'Delivery is not confirmed. Use Retry send to check safely.':'Chat is temporarily unavailable. Reconnecting automatically…'),{uncertain:write});}
  if(!r.ok||d.error)throw Object.assign(Error(errors[d.error]||'Chat is temporarily unavailable. Please try again.'),{uncertain:write&&r.status>=500});
  return d;
 }finally{clearTimeout(timeout);}
}
function lock(){if(!root)return;const blocked=sending||!!pending;composer.disabled=blocked||!people.find(p=>p.id===peer)?.active;sendButton.disabled=composer.disabled||!composer.value.trim();back.disabled=blocked;search.disabled=blocked;for(const b of roster.querySelectorAll('button'))b.disabled=blocked;older.disabled=loading;retry.hidden=!pending||sending;retry.disabled=sending;}
function renderRoster(){if(!root)return;const query=search.value.trim().toLowerCase();roster.replaceChildren();for(const p of people.filter(p=>p.id!==user&&p.email.toLowerCase().includes(query))){const b=button('',()=>choose(p.id));b.className='cu-chat-person';b.append(make('span',p.email),make('small',p.active?(p.unread?`${p.unread} unread`:'Open conversation'):'Inactive · history only'));roster.append(b);}if(!roster.childElementCount)roster.append(make('p',query?'No matching team members.':'No other team members yet.','cu-chat-empty'));lock();}
async function directory(force=false){if(!active()||!opened||directoryBusy||!force&&Date.now()-directoryAt<8000)return;const ticket=epoch;directoryBusy=true;
 try{const d=await request({op:'directory'});if(ticket!==epoch||!active())return;people=d.people;directoryAt=Date.now();const key=JSON.stringify(people);if(key!==lastPeople){lastPeople=key;renderRoster();}if(peer){title.textContent=display(peer);lock();}}
 catch(e){if(ticket===epoch)status(e.message,true);}finally{if(ticket===epoch)directoryBusy=false;}}
function renderRows(prepend=false){const bottom=atBottom(),height=log.scrollHeight,top=log.scrollTop;log.replaceChildren();for(const m of rows){const item=make('article',undefined,'cu-chat-message'+(m.sender_id===user?' cu-chat-mine':''));item.append(make('p',m.body));const t=make('time',new Intl.DateTimeFormat('en-US',{timeZone:'America/Nassau',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(new Date(m.sent_at)));t.dateTime=m.sent_at;item.append(t);log.append(item);}if(!rows.length)log.append(make('p','Start a conversation.','cu-chat-empty'));if(bottom)log.scrollTop=log.scrollHeight;else log.scrollTop=top+(prepend?Math.max(0,log.scrollHeight-height):0);}
async function markRead(){if(!visible()||!peer||!atBottom()||reading.has(peer))return;const last=rows.filter(m=>m.recipient_id===user).at(-1);if(!last||last.id<=(seen.get(peer)||0))return;const id=peer,ticket=epoch,t=threadEpoch;reading.add(id);try{await request({op:'read',peer_id:id,last_message_id:last.id,request_id:crypto.randomUUID()},true);if(ticket===epoch&&t===threadEpoch){seen.set(id,last.id);window.dispatchEvent(new CustomEvent('cu-chat-read'));}}catch{/* A later visible refresh safely retries the read marker. */}finally{if(ticket===epoch)reading.delete(id);}}
async function messages(loadOlder=false){if(!visible()||!peer||loading)return;const ticket=epoch,t=threadEpoch,id=peer;loading=true;lock();
 try{const p={op:'messages',peer_id:id};if(loadOlder&&rows.length)p.before=rows[0].id;const d=await request(p);if(ticket!==epoch||t!==threadEpoch||id!==peer||!active())return;
  const oldFirst=rows[0]?.id,oldLast=rows.at(-1)?.id;const merged=new Map([...rows,...d.data].map(m=>[m.id,m]));const next=[...merged.values()].sort((a,b)=>a.id-b.id);if(!oldFirst||loadOlder)hasMore=d.has_more;
  // When a page was hidden long enough to miss >50 messages, reload a contiguous tail.
  if(!loadOlder&&oldLast&&d.data.length===50&&!d.data.some(m=>m.id<=oldLast)){rows=d.data;hasMore=d.has_more;}else rows=next;
  const key=JSON.stringify(rows.map(m=>m.id));if(log.dataset.rows!==key||!log.childElementCount){renderRows(loadOlder);log.dataset.rows=key;}
  older.hidden=!hasMore;if(!pending)status('Messages update automatically.');await markRead();
 }catch(e){if(ticket===epoch&&t===threadEpoch)status(e.message,true);}finally{if(ticket===epoch&&t===threadEpoch){loading=false;lock();}}}
async function choose(id){if(sending||pending||!active())return;if(peer)drafts.set(peer,composer.value);peer=id;threadEpoch++;loading=false;rows=[];hasMore=false;log.replaceChildren();delete log.dataset.rows;older.hidden=true;title.textContent=display(peer);search.hidden=roster.hidden=true;conversation.hidden=false;back.hidden=false;composer.value=drafts.get(peer)||'';saveView();status('Loading conversation…');await messages();if(active()&&opened&&peer===id&&!document.hidden)composer.focus();lock();}
function list(){if(sending||pending)return;if(peer)drafts.set(peer,composer.value);peer='';threadEpoch++;loading=false;rows=[];log.replaceChildren();composer.value='';conversation.hidden=true;search.hidden=roster.hidden=false;back.hidden=true;title.textContent='Team chat';status('Choose a team member.');saveView();directory(true);search.focus();}
function toggle(value=!opened){if(!active())return;opened=value;panel.hidden=!opened;launcher.setAttribute('aria-expanded',String(opened));saveView();if(opened){directory(true);if(peer)messages();else status('Choose a team member.');(peer?composer:search).focus();}else launcher.focus();schedule();}
async function send(retrying=false){if(!active()||sending||pending&&!retrying)return;const text=composer.value.trim();if(!retrying&&(!peer||!text||!people.find(p=>p.id===peer)?.active))return;
 const work=retrying?pending:{op:'send',peer_id:peer,body:text,request_id:crypto.randomUUID()},ticket=epoch;pending=work;sending=true;lock();status('Sending…');
 try{const d=await request(work,true);if(ticket!==epoch||!active())return;pending=null;drafts.delete(work.peer_id);composer.value='';if(peer===work.peer_id&&d.data){const map=new Map([...rows,d.data].map(m=>[m.id,m]));rows=[...map.values()].sort((a,b)=>a.id-b.id);renderRows();log.scrollTop=log.scrollHeight;log.dataset.rows=JSON.stringify(rows.map(m=>m.id));}status('Sent.');window.dispatchEvent(new CustomEvent('cu-chat-sent'));}
 catch(e){if(ticket!==epoch)return;if(!e.uncertain)pending=null;status(e.message,true);}finally{if(ticket===epoch){sending=false;lock();if(!pending&&visible())composer.focus();}}}
function build(){
 root=make('aside',undefined,'cu-chat');root.id='cu-live-chat';root.setAttribute('aria-label','Team chat');
 launcher=button('',()=>toggle());launcher.id='cu-chat-launcher';launcher.className='cu-chat-launcher';launcher.setAttribute('aria-expanded','false');launcher.setAttribute('aria-controls','cu-chat-panel');launcher.append(make('span','Chat'));badge=make('span','', 'cu-chat-badge');badge.hidden=true;launcher.append(badge);
 panel=make('section',undefined,'cu-chat-panel');panel.id='cu-chat-panel';panel.setAttribute('aria-label','Team messenger');panel.hidden=true;
 const header=make('header',undefined,'cu-chat-header');back=button('‹',list);back.setAttribute('aria-label','Back to team members');back.hidden=true;title=make('h2','Team chat');const minimise=button('−',()=>toggle(false));minimise.setAttribute('aria-label','Minimise chat');header.append(back,title,minimise);panel.append(header);
 search=make('input');search.type='search';search.placeholder='Find a team member';search.setAttribute('aria-label','Find a team member');search.className='cu-chat-search';search.addEventListener('input',renderRoster);panel.append(search);
 roster=make('div',undefined,'cu-chat-roster');roster.id='cu-chat-roster';panel.append(roster);
 conversation=make('div',undefined,'cu-chat-conversation');conversation.hidden=true;older=button('Load earlier messages',()=>messages(true));older.id='cu-chat-older';older.className='cu-chat-older';older.hidden=true;log=make('div',undefined,'cu-chat-log');log.id='cu-chat-log';log.tabIndex=0;log.setAttribute('role','log');log.setAttribute('aria-label','Conversation');log.setAttribute('aria-live','polite');log.addEventListener('scroll',()=>{if(atBottom())markRead();});
 const form=make('form');form.id='cu-chat-form';form.addEventListener('submit',e=>{e.preventDefault();send();});composer=make('textarea');composer.id='cu-chat-compose';composer.rows=2;composer.maxLength=4000;composer.placeholder='Write a message…';composer.setAttribute('aria-label','Message');composer.addEventListener('input',()=>{if(peer)drafts.set(peer,composer.value);lock();});composer.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();send();}});sendButton=make('button','Send');sendButton.type='submit';form.append(composer,sendButton);conversation.append(older,log,form,make('small','Enter to send · Shift+Enter for a new line','cu-chat-hint'));panel.append(conversation);
 notice=make('p','', 'cu-chat-status');notice.id='cu-chat-status';notice.setAttribute('role','status');retry=button('Retry send',()=>send(true));retry.id='cu-chat-retry';retry.hidden=true;panel.append(notice,retry);
 const footer=make('footer');const hub=make('a','Open Team hub');hub.href='/team#messages';footer.append(hub,make('small','Direct messages are retained in the administrator’s encrypted HR backup.'));panel.append(footer);root.append(panel,launcher);document.body.append(root);
 root.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();toggle(false);}});
}
function onStatus(e){const d=e.detail;if(!area()||area().hidden||!d?.user_id)return;
 if(user!==d.user_id){if(user)clear();user=d.user_id;epoch++;build();let view;try{view=JSON.parse(sessionStorage.getItem(PREF)||'null');}catch{}if(view?.user===user){opened=!!view.open;peer=typeof view.peer==='string'&&/^[a-f0-9-]{36}$/.test(view.peer)?view.peer:'';}else{opened=false;peer='';}const selected=peer;peer='';toggle(opened);if(selected&&opened)choose(selected);else if(selected){peer=selected;title.textContent=display(peer);search.hidden=roster.hidden=true;conversation.hidden=false;back.hidden=false;}}
 const unread=Number(d.unread_messages)||0;badge.textContent=unread>99?'99+':String(unread);badge.hidden=!unread;launcher.setAttribute('aria-label',unread?`Team chat, ${unread} unread messages`:'Open team chat');if(opened)directory();schedule();
}
function schedule(){clearTimeout(timer);if(active())timer=setTimeout(tick,2000);}
async function tick(){if(polling)return schedule();if(!visible()||!peer)return schedule();polling=true;const ticket=epoch;try{await messages();}finally{if(ticket===epoch){polling=false;schedule();}}}
window.addEventListener('cu-team-status',onStatus);window.addEventListener('cu-team-clear',clear);
window.addEventListener('cu-team-offline',()=>{if(active()&&!pending)status('Connection interrupted. Reconnecting automatically…',true);});
window.addEventListener('cu-chat-open',()=>{if(active())toggle(true);});
window.addEventListener('beforeunload',e=>{if(pending||[...drafts.values()].some(s=>s.trim())){e.preventDefault();e.returnValue='';}});
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&visible()){directory(true);messages();}schedule();});
function boot(){const a=area();if(a)new MutationObserver(()=>{if(a.hidden)clear();}).observe(a,{attributes:true,attributeFilter:['hidden']});}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
