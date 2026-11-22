/* Shared navigation only. Existing page scripts continue to own every write. */
(() => {
  'use strict';
  const logo='/workspace-assets/brand/custom-u-logo.png';
  let session=null, shell=null, mobile=null, epoch=0;
  const area=()=>document.getElementById('workspace')||document.getElementById('viewer');
  function node(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
  const can=k=>session?.me?.role==='admin'||session?.me?.permissions?.[k]===true;
  const admin=()=>session?.me?.role==='admin';
  function current(href){const url=new URL(href,location.origin);return (url.pathname===location.pathname||location.pathname===url.pathname+'/new'||(url.pathname==='/products'&&location.pathname.startsWith('/products/options/'))||(url.pathname==='/quotes'&&(location.pathname==='/quotes/carryover'||location.pathname.startsWith('/quotes/shopvox/')))||(url.pathname==='/invoices'&&location.pathname.startsWith('/invoices/shopvox/'))||(url.pathname==='/products'&&/^\/products\/(?:new|[a-f0-9-]{36})$/.test(location.pathname)))&&(url.hash?url.hash===location.hash:!location.hash||!['#business-settings','#backup','#history'].includes(location.hash));}
  function hide(){shell?.remove();mobile?.remove();document.querySelector('.cu-skip')?.remove();shell=mobile=null;document.body.classList.remove('cu-layout','cu-menu-open');}
  function render(){
    const page=area();if(!session||!page||page.hidden){hide();return;}
    hide();document.body.classList.add('cu-layout');
    const main=document.querySelector('main');if(!main.id)main.id='cu-main';
    const skip=node('a','cu-skip','Skip to content');skip.href='#'+main.id;document.body.prepend(skip);
    shell=node('aside','cu-sidebar');shell.id='cu-sidebar';shell.setAttribute('aria-label','Workspace navigation');
    const brand=node('a','cu-brand');brand.href='/';brand.setAttribute('aria-label','Custom U dashboard');const img=node('img');img.src=logo;img.alt='Custom U';brand.append(img,node('small','', 'Business Manager'));shell.append(brand);
    const nav=node('nav','cu-nav');nav.setAttribute('aria-label','Main navigation');shell.append(nav);
    const enabled=!!session.crm_enabled;
    const groups=[
      ['Overview',[
        ['Dashboard','/','▦',true],['Customers','/customers','♙',enabled&&can('customers.view')],
        ['Quotes','/quotes','▤',enabled&&can('quotes.view')],['Invoices','/invoices','▣',enabled&&can('invoices.view')],
        ['Payments','/payments','↔',enabled&&can('payments.view')],['Statements','/statements','▤',enabled&&admin()],
        ['Production','/jobs','⚙',enabled&&can('jobs.view')]]],
      ['People',[['HR & time clock','/hr','◷',enabled],['Team hub','/team','▤',enabled]]],
      ['Products & proposals',[
        ['Products & pricing','/products','◈',enabled&&can('products.view')],
        ['Client mockups','/mockups','▣',enabled&&can('products.view')&&can('customers.view')],
        ['Client catalogues','/catalogues','▤',enabled&&can('products.view')&&can('customers.view')]]],
      ['Administration',[
        ['Reminders','/reminders','◷',enabled&&admin()],['Staff & access','/staff','♙',enabled&&admin()],
        ['Business settings','/quotes#business-settings','⚙',enabled&&admin()],
        ['Credits & refunds','/credits','↔',enabled&&admin()],
        ['Imported balances','/legacy-balances','▤',enabled&&admin()],
        ['Historical records','/#history','▦',admin()&&!!session.archive_configured]]],
      ['Setup & backups',[
        ['Workspace backup','/quotes#backup','↓',enabled&&admin()],
        ['Import customers','/customers/reviewed-import','↓',enabled&&admin()],
        ['Import products','/products/csv-import','↓',enabled&&admin()],
        ['Opening-balance review','/opening-balances','▤',enabled&&admin()]]]
    ];
    for(const [title,items] of groups){const visible=items.filter(x=>x[3]);if(!visible.length)continue;const group=node(title==='Setup & backups'?'details':'section','cu-nav-group');if(group.tagName==='DETAILS')group.open=visible.some(x=>current(x[1]));group.append(node(group.tagName==='DETAILS'?'summary':'h2','',title));for(const [label,href,icon] of visible){const a=node('a');a.href=href;if(current(href))a.setAttribute('aria-current','page');const glyph=node('span','cu-icon',icon);glyph.setAttribute('aria-hidden','true');a.append(glyph,node('span','',label));a.addEventListener('click',()=>closeMenu());group.append(a);}nav.append(group);}
    const user=node('div','cu-user');user.append(node('div','cu-user-email',session.me.email||''),node('div','cu-user-role',admin()?'Administrator':'Staff account'));
    const logout=node('button','','Sign out');logout.type='button';logout.addEventListener('click',()=>{const original=document.getElementById('logout');if(original){if(!original.disabled)original.click();}else location.assign('/');});user.append(logout);shell.append(user);document.body.prepend(shell);
    mobile=node('header','cu-mobilebar');const small=node('img');small.src=logo;small.alt='Custom U';const toggle=node('button','','☰ Menu');toggle.type='button';toggle.id='cu-menu-toggle';toggle.setAttribute('aria-controls','cu-sidebar');toggle.setAttribute('aria-expanded','false');toggle.addEventListener('click',()=>{const open=document.body.classList.toggle('cu-menu-open');toggle.setAttribute('aria-expanded',String(open));});mobile.append(small,toggle);document.body.prepend(mobile);
    const heading=main.querySelector(':scope > header h1');if(heading&&heading.textContent.startsWith('CUSTOM U · '))heading.textContent=heading.textContent.slice(11);
  }
  function closeMenu(){document.body.classList.remove('cu-menu-open');document.getElementById('cu-menu-toggle')?.setAttribute('aria-expanded','false');}
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&document.body.classList.contains('cu-menu-open')){closeMenu();document.getElementById('cu-menu-toggle')?.focus();}});
  window.addEventListener('hashchange',()=>{if(session)render();});
  function setSession(value){epoch++;session=value;render();}
  window.CustomUShell={setSession,clear(){epoch++;session=null;hide();window.dispatchEvent(new CustomEvent('cu-team-clear'));}};
  async function boot(){
    const page=area();if(page)new MutationObserver(()=>{if(page.hidden){hide();}else if(session&&!shell)render();}).observe(page,{attributes:true,attributeFilter:['hidden']});
    const ticket=epoch;
    try{const response=await fetch('/api/session',{credentials:'same-origin',cache:'no-store'});if(ticket!==epoch)return;if(!response.ok){session=null;hide();return;}const result=await response.json();if(ticket!==epoch)return;if(result?.me){session=result;render();}}catch{if(ticket===epoch){session=null;hide();}}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
