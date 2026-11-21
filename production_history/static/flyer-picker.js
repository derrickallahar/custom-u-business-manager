'use strict';
// Option identities only. Prices and VAT always come from authenticated product APIs.
(() => {
 const options = [{"size":"4x6","copies":100,"sides":"single","id":"d8297d4a-8440-54df-81f6-e8047e278e0b","code":"SVX-4FA93B8E07753B7781C0B428","name":"Flyers — 100 copies, 4 × 6 inches, single-sided"},{"size":"4x6","copies":100,"sides":"double","id":"84cd29d5-3971-546e-8548-755a9ea7340b","code":"SVX-B011F2F4847544EA5C77A8C8","name":"Flyers — 100 copies, 4 × 6 inches, double-sided"},{"size":"4x6","copies":250,"sides":"single","id":"f2b75a51-b305-594c-b8e3-01d00af1b411","code":"SVX-3A5DCC8D7D800C6C3F7726A7","name":"Flyers — 250 copies, 4 × 6 inches, single-sided"},{"size":"4x6","copies":250,"sides":"double","id":"b8efff0b-8403-52d3-8c8c-10bc527dc410","code":"SVX-9D55336239451C0B0373F468","name":"Flyers — 250 copies, 4 × 6 inches, double-sided"},{"size":"4x6","copies":500,"sides":"single","id":"cc55ed07-e205-5c3b-9623-097b2069bb24","code":"SVX-6610BCA3390794808EE70B01","name":"Flyers — 500 copies, 4 × 6 inches, single-sided"},{"size":"4x6","copies":500,"sides":"double","id":"6bf9705a-6106-519a-8e6d-4553cf2c392e","code":"SVX-A1CC24D2347295835109FB3F","name":"Flyers — 500 copies, 4 × 6 inches, double-sided"},{"size":"4x6","copies":1000,"sides":"single","id":"13897349-31ac-5031-85dc-638a79e3326e","code":"SVX-A5D0E714C27F2C62D31575BD","name":"Flyers — 1000 copies, 4 × 6 inches, single-sided"},{"size":"4x6","copies":1000,"sides":"double","id":"553083ca-5e7d-5e73-8e0b-d58d65101830","code":"SVX-F4ABF2D0A8E1985280B4F15F","name":"Flyers — 1000 copies, 4 × 6 inches, double-sided"},{"size":"4x6","copies":1500,"sides":"single","id":"8108f5d7-3ae1-562d-9022-112d8b02b101","code":"SVX-69B64287AE4EC34AA5447DBB","name":"Flyers — 1500 copies, 4 × 6 inches, single-sided"},{"size":"4x6","copies":1500,"sides":"double","id":"c3091fcb-9de6-5036-bb67-7c8a0d2bd8f9","code":"SVX-91D15B626ED992F665EAF446","name":"Flyers — 1500 copies, 4 × 6 inches, double-sided"},{"size":"4x6","copies":2000,"sides":"single","id":"cd6c0445-dcbe-5acf-9a86-460297eab9cf","code":"SVX-0F3A4874A2E5A57B4F8DD897","name":"Flyers — 2000 copies, 4 × 6 inches, single-sided"},{"size":"4x6","copies":2000,"sides":"double","id":"5051560f-6bbc-59df-a457-ff75073075e0","code":"SVX-71E9F8EED411B9DC78546059","name":"Flyers — 2000 copies, 4 × 6 inches, double-sided"},{"size":"5x7","copies":100,"sides":"single","id":"5ff60d82-9d5c-5cfa-851c-6e2aac199514","code":"SVX-90BDDB2FF70FE5E70ECADF6B","name":"Flyers — 100 copies, 5 × 7 inches, single-sided"},{"size":"5x7","copies":100,"sides":"double","id":"52b196c7-edc4-5726-bdb9-9eec35873228","code":"SVX-23E10069073DEBF23D36CDB6","name":"Flyers — 100 copies, 5 × 7 inches, double-sided"},{"size":"5x7","copies":250,"sides":"single","id":"f279cabb-1da6-5a83-ae3b-8e70fdec71b0","code":"SVX-C55EEC27D61287D05BFD8C1D","name":"Flyers — 250 copies, 5 × 7 inches, single-sided"},{"size":"5x7","copies":250,"sides":"double","id":"c7f06e22-8d6b-53f4-b22c-e7847bb5d4d3","code":"SVX-9944403D74A977ECC6AA57D7","name":"Flyers — 250 copies, 5 × 7 inches, double-sided"},{"size":"5x7","copies":500,"sides":"single","id":"a1703936-afae-55b1-afc8-66c60932d910","code":"SVX-7594F1C6DAD4E4B9D7C2054F","name":"Flyers — 500 copies, 5 × 7 inches, single-sided"},{"size":"5x7","copies":500,"sides":"double","id":"9a9438d9-df1a-5c75-a3dd-a7aabdfbfc23","code":"SVX-73EBF0B50EC0F162E01DE911","name":"Flyers — 500 copies, 5 × 7 inches, double-sided"},{"size":"5x7","copies":1000,"sides":"single","id":"32d422c1-1370-5031-872b-5841350a8e41","code":"SVX-FE06FA215CF3363001EDDCDC","name":"Flyers — 1000 copies, 5 × 7 inches, single-sided"},{"size":"5x7","copies":1000,"sides":"double","id":"053557ed-55fe-543c-8524-226d5a4a95e2","code":"SVX-F118929D698747F67952192C","name":"Flyers — 1000 copies, 5 × 7 inches, double-sided"},{"size":"5x7","copies":1500,"sides":"single","id":"3a5da004-be5e-540b-90c5-f8003b6bb449","code":"SVX-02FA5A18950C795C992EA6FA","name":"Flyers — 1500 copies, 5 × 7 inches, single-sided"},{"size":"5x7","copies":1500,"sides":"double","id":"20d37b1a-6db5-5291-b458-7e13d19fe487","code":"SVX-4B1881F107CE9CACB3E6CE05","name":"Flyers — 1500 copies, 5 × 7 inches, double-sided"},{"size":"5x7","copies":2000,"sides":"single","id":"130322f9-6c74-59a0-98b8-a153abc00c14","code":"SVX-74CD7B4D594BCEFB293F0B29","name":"Flyers — 2000 copies, 5 × 7 inches, single-sided"},{"size":"5x7","copies":2000,"sides":"double","id":"5c523eb2-16f5-5d09-816e-4855ee52a539","code":"SVX-0C7E262E811F20FE7E86B24C","name":"Flyers — 2000 copies, 5 × 7 inches, double-sided"},{"size":"8x11","copies":100,"sides":"single","id":"21f00597-d4da-57bd-a3c5-706dfde7c173","code":"SVX-40D2ED549E018DAB4DF4F9DA","name":"Flyers — 100 copies, 8 × 11 inches, single-sided"},{"size":"8x11","copies":100,"sides":"double","id":"cc0b8428-f2a2-5a26-9f79-d46370ae01a1","code":"SVX-9DFAD7CFBFBBBF31983ECAF6","name":"Flyers — 100 copies, 8 × 11 inches, double-sided"},{"size":"8x11","copies":250,"sides":"single","id":"ff4a4bfc-f836-5323-923e-4c387e163f13","code":"SVX-CCE1C760441646780B46C353","name":"Flyers — 250 copies, 8 × 11 inches, single-sided"},{"size":"8x11","copies":250,"sides":"double","id":"905f7be3-a8b8-541e-980f-87404c0c88ae","code":"SVX-D89822A3AC57D33AA1DA341A","name":"Flyers — 250 copies, 8 × 11 inches, double-sided"},{"size":"8x11","copies":500,"sides":"single","id":"6d6cd68d-b70e-51ae-8e58-644593b99db6","code":"SVX-276B2ABC540779594A96ED0D","name":"Flyers — 500 copies, 8 × 11 inches, single-sided"},{"size":"8x11","copies":500,"sides":"double","id":"a588ea51-9af6-51de-a8bc-765166ed3ab9","code":"SVX-1C21EAFF19172841BA3BE48A","name":"Flyers — 500 copies, 8 × 11 inches, double-sided"},{"size":"8x11","copies":1000,"sides":"single","id":"cfb7d57a-3c68-59b4-bb91-018b4e77f558","code":"SVX-790B940EBE26F7F469C8FC4A","name":"Flyers — 1000 copies, 8 × 11 inches, single-sided"},{"size":"8x11","copies":1000,"sides":"double","id":"be589b3a-7a1d-59f7-a839-2f5730890ede","code":"SVX-E5606996198C6ED955435FA5","name":"Flyers — 1000 copies, 8 × 11 inches, double-sided"},{"size":"8x11","copies":1500,"sides":"single","id":"29aa0421-40bb-59fe-9ab5-23b10687ba40","code":"SVX-18A854C5F6FB9ED3C95F68D0","name":"Flyers — 1500 copies, 8 × 11 inches, single-sided"},{"size":"8x11","copies":1500,"sides":"double","id":"d0a6906f-8f04-53c6-bbfe-af4438f18af9","code":"SVX-C39896C2D33D6CAA3107B3BF","name":"Flyers — 1500 copies, 8 × 11 inches, double-sided"},{"size":"8x11","copies":2000,"sides":"single","id":"5b988858-720b-537b-be9d-9fba5fa3bb29","code":"SVX-3B45EF4C9CCCD34E31AF0669","name":"Flyers — 2000 copies, 8 × 11 inches, single-sided"},{"size":"8x11","copies":2000,"sides":"double","id":"898dfbea-18f2-54e0-a30a-6d4a66c8e753","code":"SVX-F9D5E1B475D6CDEE30454487","name":"Flyers — 2000 copies, 8 × 11 inches, double-sided"},{"size":"4.5x9","copies":100,"sides":"single","id":"c3bb1793-8133-5c49-8a33-fc666739d560","code":"SVX-619F7A76852FBF99F1B81AEC","name":"Flyers — 100 copies, 4.5 × 9 inches, single-sided"},{"size":"4.5x9","copies":100,"sides":"double","id":"8cf73cf5-1dec-589b-97a7-8c91310fe403","code":"SVX-565D616703F6E94EDA484521","name":"Flyers — 100 copies, 4.5 × 9 inches, double-sided"},{"size":"4.5x9","copies":250,"sides":"single","id":"9fb47de3-f64a-5cbd-aba9-ee836ffabc0c","code":"SVX-13C07701DBD99814200CD85A","name":"Flyers — 250 copies, 4.5 × 9 inches, single-sided"},{"size":"4.5x9","copies":250,"sides":"double","id":"c2057ef4-ee31-5098-813b-522f2878c44e","code":"SVX-795EA821A84D046C04DCD951","name":"Flyers — 250 copies, 4.5 × 9 inches, double-sided"},{"size":"4.5x9","copies":500,"sides":"single","id":"ba8cd60f-376d-5423-a452-640b754482b0","code":"SVX-B44EDD7092F37D0938703D38","name":"Flyers — 500 copies, 4.5 × 9 inches, single-sided"},{"size":"4.5x9","copies":500,"sides":"double","id":"6bf11236-4cdf-5bcf-8abf-3b68cd54a40d","code":"SVX-69522B3C8F3BFEAFD8BFBE96","name":"Flyers — 500 copies, 4.5 × 9 inches, double-sided"},{"size":"4.5x9","copies":1000,"sides":"single","id":"8a777a0f-8ca2-58d2-a055-f8f77bdac94b","code":"SVX-0E125D541D5681766BE42C08","name":"Flyers — 1000 copies, 4.5 × 9 inches, single-sided"},{"size":"4.5x9","copies":1000,"sides":"double","id":"fd7ede31-4705-520e-9ff0-ea0dfb83eacf","code":"SVX-43618F8E1BD7787C8B724908","name":"Flyers — 1000 copies, 4.5 × 9 inches, double-sided"},{"size":"4.5x9","copies":1500,"sides":"single","id":"6c057e45-6007-5dc5-a3ab-3722426ee5c6","code":"SVX-4A7A19AF345E2A7D29AB1317","name":"Flyers — 1500 copies, 4.5 × 9 inches, single-sided"},{"size":"4.5x9","copies":1500,"sides":"double","id":"6970d17d-606c-5296-ba6e-4704c24c8568","code":"SVX-D030D318637F38CD99A6EF6B","name":"Flyers — 1500 copies, 4.5 × 9 inches, double-sided"},{"size":"4.5x9","copies":2000,"sides":"single","id":"2044700c-67cd-5804-8533-c09485b4c741","code":"SVX-4D7AADE337C7BBEF2DC3B51C","name":"Flyers — 2000 copies, 4.5 × 9 inches, single-sided"},{"size":"4.5x9","copies":2000,"sides":"double","id":"54ca70a4-e2e3-5f93-9a10-4ec7f3099bb3","code":"SVX-A5768D4007EC2F34BD51761B","name":"Flyers — 2000 copies, 4.5 × 9 inches, double-sided"}];
 const sizes = [['4x6','4 × 6 inches'],['5x7','5 × 7 inches'],['8x11','8 × 11 inches'],['4.5x9','4.5 × 9 inches']];
 const byId = new Map(options.map(o=>[o.id,o]));
 const hundred = raw => {const [a,b='']=raw.split('.');return BigInt(a)*100n+BigInt(b.padEnd(2,'0'));};
 const cash = cents => 'BSD '+(Number(cents)/100).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
 function valid(product, option) {
  const d=product?.data;
  return !!(option && product?.active===true && product.id===option.id && d?.code===option.code &&
   !d.pricing && d.name===option.name && d.unit==='Run' && typeof d.unit_price==='string' &&
   /^[0-9]{1,7}(\.[0-9]{1,2})?$/.test(d.unit_price) && Number(d.unit_price)>0 && Number(d.unit_price)<=1000000 &&
   typeof d.vat_rate==='string' && /^[0-9]{1,3}(\.[0-9]{1,2})?$/.test(d.vat_rate) && Number(d.vat_rate)<=100);
 }
 function mount({root,api,run,editable,onAdd}) {
  if(!root) return null;
  let saved=new Map(),loaded=false;
  const find=name=>root.querySelector('[data-flyer="'+name+'"]');
  const load=find('load'),size=find('size'),side=find('side'),copies=find('copies'),add=find('add'),price=find('price'),note=find('note');
  function fill(select,values,placeholder){
   select.replaceChildren(new Option(placeholder,''));
   for(const [v,t] of values)select.add(new Option(t,String(v)));
  }
  fill(size,sizes,'Choose size');fill(side,[['single','Single-sided'],['double','Double-sided']],'Choose sides');
  fill(copies,[100,250,500,1000,1500,2000].map(q=>[q,q+' copies']),'Choose run quantity');
  const fifty=new Option('50 copies — price unavailable','50');fifty.disabled=true;copies.add(fifty,1);
  const chosen=()=>options.find(o=>o.size===size.value&&o.sides===side.value&&String(o.copies)===copies.value);
  function update(){
   const enabled=editable(),o=chosen(),p=o?saved.get(o.id):null;
   load.disabled=!enabled;size.disabled=!enabled||!loaded;side.disabled=!enabled||!loaded;copies.disabled=!enabled||!loaded;
   add.disabled=!enabled||!valid(p,o);
   // Also restore unavailable options after the surrounding form re-enables controls.
   fifty.disabled=true;
   price.textContent='';
   if(valid(p,o)){
    const cents=hundred(p.data.unit_price),vat=(cents*hundred(p.data.vat_rate)+5000n)/10000n;
    price.textContent='One run: '+cash(cents)+' before VAT + '+cash(vat)+' VAT ('+p.data.vat_rate+'%) = '+cash(cents+vat)+'.';
   }else if(o&&loaded)price.textContent='This run is not available in the saved catalogue. Import it or review its product record first.';
  }
  function clear(){saved.clear();loaded=false;size.value='';side.value='';copies.value='';price.textContent='';note.textContent='Load the saved prices, then choose a flyer run.';update();}
  load.onclick=()=>run(async()=>{
   if(!editable(true))return;
   saved.clear();loaded=false;price.textContent='';note.textContent='Loading saved flyer prices…';
   try{
    let page=1,total=0;
    do{
     const r=await api('/api/products?q=Flyers&state=active&page='+page);
     if(!Array.isArray(r.data)||!Number.isInteger(r.total)||r.total<0||r.total>5000||r.data.length>50)
      throw Error('The saved flyer prices could not be verified. Load prices again.');
     total=r.total;
     for(const p of r.data){const o=byId.get(p.id);if(valid(p,o))saved.set(p.id,p);}
     page++;
    }while((page-1)*50<total);
    loaded=true;
    note.textContent=saved.size+' of 48 priced flyer options available. Fifty-copy runs are unavailable. Prices are for the whole run.';
   }catch(error){saved.clear();note.textContent='Prices could not be loaded. Try loading them again.';throw error;}
   finally{update();}
  });
  for(const select of [size,side,copies])select.onchange=update;
  add.onclick=()=>run(async()=>{
   if(!editable(true))return;
   const o=chosen(),p=o?saved.get(o.id):null;
   if(!valid(p,o))throw Error('Choose an available flyer run first.');
   const current=(await api('/api/products/'+o.id)).data;
   if(!valid(current,o)){
    saved.delete(o.id);update();
    throw Error('This flyer run was archived or its identifying details changed. Review the product before using it.');
   }
   // A price change is shown for review instead of silently adding a different price.
   if(JSON.stringify(current.data)!==JSON.stringify(p.data)){
    saved.set(o.id,current);update();
    throw Error('The saved flyer price or details changed. Review the updated price, then add the run again.');
   }
   const d=current.data,description=[d.name,d.description].filter(Boolean).join('\n');
   if(description.length>1000)throw Error('The flyer description is too long. Shorten it in Products first.');
   onAdd({description,quantity:'1',unit:'Run',unit_price:d.unit_price,vat_rate:d.vat_rate,discount_percent:'0',finish:d.finish,placement:d.placement});
  });
  clear();
  return {clear,update};
 }
 window.CustomUFlyerPicker=Object.freeze({mount});
})();
