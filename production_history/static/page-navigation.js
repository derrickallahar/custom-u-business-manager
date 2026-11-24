/* Keep navigation in the current browsing context; never perform business writes. */
(() => {
 'use strict';
 function navigable(a){
  const href=a.getAttribute('href');
  if(!href||href.startsWith('#')||a.hasAttribute('download')||a.classList.contains('cu-skip'))return false;
  try{return ['http:','https:','blob:'].includes(new URL(href,location.href).protocol);}catch{return false;}
 }
 function prepare(a){if(navigable(a)){a.target='_self';a.relList.add('noopener');}}
 function scan(node){if(node.nodeType!==1)return;if(node.matches('a[href]'))prepare(node);for(const a of node.querySelectorAll('a[href]'))prepare(a);}
 function open(url){const target=new URL(url,location.origin);if(target.origin!==location.origin||!['http:','https:'].includes(target.protocol))return;window.open(target.href,'_self');}
 window.CustomUNavigation={open};
 document.addEventListener('click',event=>{
  const anchor=event.target.closest?.('a[href]');if(anchor){prepare(anchor);return;}
  const button=event.target.closest?.('button');if(!button||button.matches(':disabled')||button.closest('[hidden]'))return;
  let url=button.dataset.openPage;
  const feature=location.pathname.split('/')[1];
  const ids={quotes:'new',invoices:'new-invoice',customers:'new-customer',jobs:'new-job',mockups:'new',catalogues:'new',products:'new'};
  if(!url&&button.id===ids[feature]){
   url='/'+feature+'/new';
   if(feature==='jobs')url+='?mode='+encodeURIComponent(document.getElementById('mode')?.value==='live'?'live':'test');
   if(feature==='products')url+=location.search;
  }
  if(url){event.preventDefault();event.stopImmediatePropagation();open(url);}
 },true);
 scan(document.documentElement);
 new MutationObserver(records=>{for(const r of records){if(r.type==='attributes')scan(r.target);else for(const n of r.addedNodes)scan(n);}}).observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['href']});
})();
