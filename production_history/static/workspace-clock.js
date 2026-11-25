/* One own-attendance control shared by every authenticated workspace page. */
(() => {
  'use strict';
  let host=null, data=null, pending=null, busy=false, reading=false, error='', message='', epoch=0, seen=0, key=null;
  const prefix='customu.clock.pending.129.';
  const node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
  const errors={MISSED_CLOCK_OUT:'This shift needs a manager correction in HR.',SHIFT_CORRECTED:'Today’s shift was corrected and closed. Ask your manager to review it.',ALREADY_CLOCKED_IN:'You are already clocked in.',NOT_CLOCKED_IN:'You are already clocked out.',ACCESS_DENIED:'Clock access is unavailable. Sign in again or contact your administrator.',APPROVED_COMPUTER_REQUIRED:'Use an approved work computer.',APPROVED_NETWORK_REQUIRED:'Connect to an approved network.',LOGIN_REQUIRED:'Please sign in again.'};
  const time=value=>new Intl.DateTimeFormat('en-US',{timeZone:'America/Nassau',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(new Date(value));
  const currentNow=()=>Date.parse(data.now)+Math.max(0,performance.now()-seen);
  const missed=()=>data?.shift?.state==='in'&&currentNow()-Date.parse(data.shift.last_in)>86400000;
  function position(){if(!host)return;const mobile=document.querySelector('.cu-mobilebar'),brand=document.querySelector('.cu-brand');if(matchMedia('(max-width:760px)').matches&&mobile)mobile.prepend(host);else if(brand)brand.after(host);}
  function render(){
    if(!host)return;position();host.replaceChildren();
    const title=node('small','MY TIME CLOCK'),status=node('strong',!data?'Status unavailable':missed()?'Missed clock-out':data.shift?.state==='in'?'Clocked in':'Clocked out');status.className='cu-clock-state';status.dataset.state=data?.shift?.state||'unknown';
    host.append(title,status);
    if(data?.shift?.state==='in')host.append(node('span','Since '+time(data.shift.last_in)+' · Nassau'));
    const feedback=node('p',error||message||(!data?'Checking your saved status…':missed()?'Open HR to correct this shift.':data.shift?.corrected?'Today’s shift is closed after correction.':'Your time is saved in Nassau time.'));
    feedback.setAttribute('role','status');feedback.setAttribute('aria-live','polite');host.append(feedback);
    const action=node('button',busy?'Saving…':pending?'Retry '+(pending.op==='clock_in'?'clock-in':'clock-out'):!data||error?'Refresh status':missed()||data.shift?.corrected?'Open time records':data.shift?.state==='in'?'Clock out':'Clock in');action.type='button';action.disabled=busy||reading;
    action.addEventListener('click',()=>{if(pending)retry();else if(!data||error)refresh(true);else if(missed()||data.shift?.corrected)location.assign('/hr');else act(data.shift?.state==='in'?'clock_out':'clock_in');});host.append(action);
    if(['unreported','pending','clarification'].includes(data?.shift?.early_review_status)){const review=node('a','Early time needs review — open HR');review.href='/hr';host.append(review);}
    host.setAttribute('aria-busy',String(busy));
  }
  async function request(url,payload){
    const abort=new AbortController(),timeout=setTimeout(()=>abort.abort(),15000);
    try{
      const r=await fetch(url,{method:payload?'POST':'GET',credentials:'same-origin',cache:'no-store',signal:abort.signal,headers:payload?{'Content-Type':'application/json'}:undefined,body:payload?JSON.stringify(payload):undefined});
      let d;try{d=await r.json();}catch{throw {uncertain:!!payload,message:'The response was interrupted. Your action is not confirmed.'};}
      if(!r.ok||d.error)throw {uncertain:!!payload&&r.status>=500,denied:r.status===401||r.status===403,message:errors[d.error]||'The time clock could not be updated. Refresh or contact your administrator.'};
      return d;
    }catch(e){if(e.message&&'uncertain' in e)throw e;throw {uncertain:!!payload,message:payload?'Connection interrupted. Retry to check the same action safely.':'Could not refresh your clock status. Check your connection.'};}
    finally{clearTimeout(timeout);}
  }
  function restore(){
    key=prefix+data.user_id;
    try{const p=JSON.parse(sessionStorage.getItem(key)||'null');pending=p&&['clock_in','clock_out'].includes(p.op)&&/^[0-9a-f-]{36}$/.test(p.request_id)?{op:p.op,request_id:p.request_id}:null;}catch{pending=null;}
  }
  function clearPending(){try{if(key)sessionStorage.removeItem(key);}catch{}pending=null;}
  async function refresh(manual=false){
    if(!host||reading||busy)return false;const ticket=epoch;reading=true;if(manual){error='';message='';}render();
    try{const result=await request('/api/hr/clock');if(ticket!==epoch)return false;
      if(!result.user_id||!Number.isFinite(Date.parse(result.now)))throw {message:'Could not read your saved clock status.'};
      data=result;seen=performance.now();error='';restore();return true;
    }catch(e){if(ticket===epoch){error=e.message;data=null;if(e.denied){pending=null;message='';}}return false;}
    finally{if(ticket===epoch){reading=false;render();}}
  }
  async function write(payload){
    if(!host||busy||reading||!data)return;const ticket=epoch,storageKey=key;
    try{sessionStorage.setItem(storageKey,JSON.stringify(payload));}catch{error='Enable browser storage before clocking in or out, so an interrupted save can be recovered.';render();return;}
    pending=payload;busy=true;error='';message='';render();let saved=false;
    try{const result=await request('/api/hr/action',payload);
      if(!result?.data?.id||!result.data.data?.state)throw {uncertain:true,message:'The saved result was not confirmed. Retry the same action.'};
      // The receipt belongs to this account even if navigation hid the panel meanwhile.
      try{if(sessionStorage.getItem(storageKey)===JSON.stringify(payload))sessionStorage.removeItem(storageKey);}catch{}
      if(ticket!==epoch)return;pending=null;saved=true;message=payload.op==='clock_in'?'Clock-in saved.':'Clock-out saved.';
    }catch(e){if(ticket!==epoch)return;error=e.message;if(!e.uncertain)clearPending();if(e.denied)data=null;}
    finally{if(ticket===epoch){busy=false;render();if(saved){window.dispatchEvent(new CustomEvent('cu-attendance-changed',{detail:{source:'sidebar'}}));await refresh();}else if(data&&!pending){const failure=error;await refresh();error=failure;render();}}}
  }
  async function retry(){if(!data&&!await refresh())return;if(pending)await write(pending);}
  async function act(op){
    if(!host||busy||reading)return;if(pending){error='Resolve the unconfirmed clock action with Retry first.';render();return;}
    if(!await refresh()||pending)return;
    const expected=data.shift?.state==='in'?'clock_out':'clock_in';
    if(op!==expected||missed()||data.shift?.corrected){message='Your clock status has changed. Review it before continuing.';render();return;}
    await write({op,request_id:crypto.randomUUID()});
  }
  function unmount(){epoch++;host=null;data=null;pending=null;key=null;reading=busy=false;message=error='';}
  function mount(element){unmount();if(!element)return;host=element;render();refresh();}
  window.CustomUClock={mount,unmount,action:act};
  window.addEventListener('cu-attendance-changed',e=>{if(e.detail?.source!=='sidebar')refresh();});
  window.addEventListener('focus',()=>refresh());
  window.addEventListener('resize',position);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
  setInterval(()=>{if(!document.hidden)refresh();},60000);
  mount(document.getElementById('cu-clock'));
})();
