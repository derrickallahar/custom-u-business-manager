'use strict';
// Option identities only. Prices and VAT always come from authenticated product APIs.
(() => {
 const options = [{"format": "single", "copies": 50, "code": "SVX-D7C5ACBC62706922F4C7CE5D", "name": "Brochures — 50 copies, single-sided, unfolded, 100 lb text", "id": "deb6200e-ccda-5058-a51c-fb7a0a95fd0e"}, {"format": "double", "copies": 50, "code": "SVX-5CB11F3B86D674C253A1D7D5", "name": "Brochures — 50 copies, double-sided, unfolded, 100 lb text", "id": "5f063f21-fa4b-545a-88a5-b802026c916d"}, {"format": "bi", "copies": 50, "code": "SVX-F402E6B7C0C8813DF485C91B", "name": "Brochures — 50 copies, bi-fold, double-sided, 100 lb text", "id": "ce997735-98ff-5979-8c1b-4c7eb039492a"}, {"format": "tri", "copies": 50, "code": "SVX-353E744E63770D26A5D5517D", "name": "Brochures — 50 copies, tri-fold, double-sided, 100 lb text", "id": "2cef0eda-f461-51d2-a9f3-fd54f359b275"}, {"format": "z", "copies": 50, "code": "SVX-A214C2533DAB50CDCBD8CFF1", "name": "Brochures — 50 copies, z-fold, double-sided, 100 lb text", "id": "a1b96e0a-fa22-5619-87c3-1e7098aec332"}, {"format": "single", "copies": 100, "code": "SVX-629304198AC45DC48A187185", "name": "Brochures — 100 copies, single-sided, unfolded, 100 lb text", "id": "10d54ddc-b12b-58cc-bc31-05298ee8602c"}, {"format": "double", "copies": 100, "code": "SVX-4903E94300007D108A08859B", "name": "Brochures — 100 copies, double-sided, unfolded, 100 lb text", "id": "33746a4f-b61e-5018-b092-0a03c3bd01d3"}, {"format": "bi", "copies": 100, "code": "SVX-528E08D5DA1DAD41B8921E72", "name": "Brochures — 100 copies, bi-fold, double-sided, 100 lb text", "id": "d88ef2cc-e9ee-5f11-ab0a-26c4caf6d8a6"}, {"format": "tri", "copies": 100, "code": "SVX-6DFF77F9F5372FB767880B0B", "name": "Brochures — 100 copies, tri-fold, double-sided, 100 lb text", "id": "7e94838d-0a9d-5d13-a242-1b95187578ab"}, {"format": "z", "copies": 100, "code": "SVX-7532F1E712E531853AA76911", "name": "Brochures — 100 copies, z-fold, double-sided, 100 lb text", "id": "c8c37791-573b-589d-a3bf-693200b2e404"}, {"format": "single", "copies": 250, "code": "SVX-49B86502987BBDEF243062BE", "name": "Brochures — 250 copies, single-sided, unfolded, 100 lb text", "id": "21c0e649-9147-552f-9b59-6a189c5f9a0e"}, {"format": "double", "copies": 250, "code": "SVX-66963004EBEB406C1C4A0508", "name": "Brochures — 250 copies, double-sided, unfolded, 100 lb text", "id": "b8b11ff1-30e1-54e5-b912-40746e83cf65"}, {"format": "bi", "copies": 250, "code": "SVX-F0E20D72FBDDE3E941352B38", "name": "Brochures — 250 copies, bi-fold, double-sided, 100 lb text", "id": "abfb0029-2032-591e-ac81-7e6e4a939f31"}, {"format": "tri", "copies": 250, "code": "SVX-5552E83891C5B6DA7BE7C5E1", "name": "Brochures — 250 copies, tri-fold, double-sided, 100 lb text", "id": "3dd0787d-d510-5524-ba67-7ed0ddc63795"}, {"format": "z", "copies": 250, "code": "SVX-2A4606E66D36A5057B65A1CC", "name": "Brochures — 250 copies, z-fold, double-sided, 100 lb text", "id": "eb2a039a-941a-58a4-a861-826922f469f5"}, {"format": "single", "copies": 500, "code": "SVX-0A0A5805F94815148B3997EC", "name": "Brochures — 500 copies, single-sided, unfolded, 100 lb text", "id": "cab1a46a-8172-5dea-9842-e351cc7a18f6"}, {"format": "double", "copies": 500, "code": "SVX-C57B92E5C954C13D33AB4856", "name": "Brochures — 500 copies, double-sided, unfolded, 100 lb text", "id": "5574dcab-89c1-5002-a5e9-2001340bb6de"}, {"format": "bi", "copies": 500, "code": "SVX-B3C4809353BDDFC31F71DBD8", "name": "Brochures — 500 copies, bi-fold, double-sided, 100 lb text", "id": "e90b0dd6-49ca-5cb0-ab7e-aea0eeff1132"}, {"format": "tri", "copies": 500, "code": "SVX-3C5CD1D688E96FD255B35568", "name": "Brochures — 500 copies, tri-fold, double-sided, 100 lb text", "id": "d4de0566-d697-5a64-8c1f-045e6f12bbbb"}, {"format": "z", "copies": 500, "code": "SVX-C35AA38A5D64B710F5680075", "name": "Brochures — 500 copies, z-fold, double-sided, 100 lb text", "id": "10e06ea5-9173-504a-93c8-3d8a3c032c9c"}, {"format": "single", "copies": 1000, "code": "SVX-6DD2900504017B900BD3FD4E", "name": "Brochures — 1000 copies, single-sided, unfolded, 100 lb text", "id": "f1605253-e51d-5ab0-b63e-8b8b378b246f"}, {"format": "double", "copies": 1000, "code": "SVX-A651779E432800E11582EFD4", "name": "Brochures — 1000 copies, double-sided, unfolded, 100 lb text", "id": "bc97d4dd-17fa-5f29-aa8c-d206b8b6898a"}, {"format": "bi", "copies": 1000, "code": "SVX-C34D7055ABE0B15D03703204", "name": "Brochures — 1000 copies, bi-fold, double-sided, 100 lb text", "id": "811c1830-87a5-56d4-bd15-ec12dc1a2d85"}, {"format": "tri", "copies": 1000, "code": "SVX-F19CF318F86E1F15C77A5A9D", "name": "Brochures — 1000 copies, tri-fold, double-sided, 100 lb text", "id": "92455357-b52e-5f71-8117-38e491c4480f"}, {"format": "z", "copies": 1000, "code": "SVX-D66C63E09ECF3E6B03D30A23", "name": "Brochures — 1000 copies, z-fold, double-sided, 100 lb text", "id": "58dc4deb-2f14-5f7e-baed-7a0522f6517c"}, {"format": "single", "copies": 1500, "code": "SVX-2EF0FAAB3BEC2B42C045DC00", "name": "Brochures — 1500 copies, single-sided, unfolded, 100 lb text", "id": "dd0357b2-8335-5460-b8db-4521e866a749"}, {"format": "double", "copies": 1500, "code": "SVX-3CC6AA77A76751B536682C60", "name": "Brochures — 1500 copies, double-sided, unfolded, 100 lb text", "id": "422d739b-e907-5ec1-aa51-14db64d51b3a"}, {"format": "bi", "copies": 1500, "code": "SVX-921D7ABBB8F040E0DDFBDD05", "name": "Brochures — 1500 copies, bi-fold, double-sided, 100 lb text", "id": "08b3ca31-0021-5f03-b53c-392350b48e4c"}, {"format": "tri", "copies": 1500, "code": "SVX-53E00A7D8D8191FEF6F484A2", "name": "Brochures — 1500 copies, tri-fold, double-sided, 100 lb text", "id": "27dba972-34df-5116-b9f3-3769ce08a1af"}, {"format": "z", "copies": 1500, "code": "SVX-AD3A65F8CCB6901D01E13A06", "name": "Brochures — 1500 copies, z-fold, double-sided, 100 lb text", "id": "e09d5d12-388b-5d21-93a4-cc01aec78f97"}, {"format": "single", "copies": 2000, "code": "SVX-B141928A2DC8F5F984DF0243", "name": "Brochures — 2000 copies, single-sided, unfolded, 100 lb text", "id": "5a955fe8-5685-57e6-8c87-d977a81a6aa7"}, {"format": "double", "copies": 2000, "code": "SVX-24F9DF22C714D10DB53FD353", "name": "Brochures — 2000 copies, double-sided, unfolded, 100 lb text", "id": "e9b8a671-0bb5-5f83-a9c9-939099240ad1"}, {"format": "bi", "copies": 2000, "code": "SVX-16FB44C79708EA5A43B0EAF9", "name": "Brochures — 2000 copies, bi-fold, double-sided, 100 lb text", "id": "5d8b5f01-6658-5e93-bdad-4c05fa15c22c"}, {"format": "tri", "copies": 2000, "code": "SVX-131845192B303EB7A3D1BB74", "name": "Brochures — 2000 copies, tri-fold, double-sided, 100 lb text", "id": "06c73f20-8f4f-5f89-b2c3-1f6c5cefa3a6"}, {"format": "z", "copies": 2000, "code": "SVX-E8FBF2AE7E6AB5025DAD0719", "name": "Brochures — 2000 copies, z-fold, double-sided, 100 lb text", "id": "e9212640-9267-56a6-a49f-ffba3e8e9085"}, {"format": "single", "copies": 3000, "code": "SVX-91F78504C624B9F8CAF1A212", "name": "Brochures — 3000 copies, single-sided, unfolded, 100 lb text", "id": "f3acfc55-77cb-5920-a9cf-2e0276b0ade2"}, {"format": "double", "copies": 3000, "code": "SVX-B47BA7904D1A1AC86D713129", "name": "Brochures — 3000 copies, double-sided, unfolded, 100 lb text", "id": "d9637e55-ee04-5f18-ab2d-ec0708ef364b"}, {"format": "bi", "copies": 3000, "code": "SVX-2CD17828F093A0A665AEB575", "name": "Brochures — 3000 copies, bi-fold, double-sided, 100 lb text", "id": "f947319b-2643-58b6-93be-007e57d1c9e1"}, {"format": "tri", "copies": 3000, "code": "SVX-0886481D6741705644CF3E02", "name": "Brochures — 3000 copies, tri-fold, double-sided, 100 lb text", "id": "f2ffc681-9431-57e1-95a2-99259f5dc3e2"}, {"format": "z", "copies": 3000, "code": "SVX-00AA7186F0FB42C260FB2DA1", "name": "Brochures — 3000 copies, z-fold, double-sided, 100 lb text", "id": "e547e2ec-cc03-58c2-9794-3e093c30c7da"}];
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
  let saved=new Map(),loaded=false,revision=0,focusPending=false;
  const find=name=>root.querySelector('[data-brochure="'+name+'"]');
  const load=find('load'),format=find('format'),copies=find('copies'),add=find('add'),price=find('price'),note=find('note');
  function fill(select,values,placeholder){
   select.replaceChildren(new Option(placeholder,''));
   for(const [v,t] of values)select.add(new Option(t,String(v)));
  }
  fill(format,[["single", "Single-sided, unfolded"], ["double", "Double-sided, unfolded"], ["bi", "Bi-fold, double-sided"], ["tri", "Tri-fold, double-sided"], ["z", "Z-fold, double-sided"]],'Choose printing / fold');
  fill(copies,[50,100,250,500,1000,1500,2000,3000].map(q=>[q,q+' copies']),'Choose run quantity');
  const chosen=()=>options.find(o=>o.format===format.value&&String(o.copies)===copies.value);
  function update(){
   const enabled=editable(),o=chosen(),p=o?saved.get(o.id):null;
   load.disabled=!enabled;format.disabled=!enabled||!loaded;copies.disabled=!enabled||!loaded;
   add.disabled=!enabled||!valid(p,o);
   if(enabled&&loaded&&focusPending)queueMicrotask(()=>{if(focusPending&&editable()&&!format.matches(':disabled')){focusPending=false;format.focus();}});
   price.textContent='';
   if(valid(p,o)){
    const cents=hundred(p.data.unit_price),vat=(cents*hundred(p.data.vat_rate)+5000n)/10000n;
    price.textContent='One run: '+cash(cents)+' before VAT + '+cash(vat)+' VAT ('+p.data.vat_rate+'%) = '+cash(cents+vat)+'.';
   }else if(o&&loaded)price.textContent='This run is not available in the saved catalogue. Import it or review its product record first.';
  }
  function clear(){revision++;focusPending=false;saved.clear();loaded=false;format.value='';copies.value='';price.textContent='';note.textContent='Load the saved prices, then choose a brochure run.';update();}
  async function loadPrices(){
   if(!editable(true))return;
   const start=++revision,next=new Map();
   saved.clear();loaded=false;price.textContent='';note.textContent='Loading saved brochure prices…';
   try{
    let page=1,total=0;
    do{
     const r=await api('/api/products?q=Brochures&state=active&page='+page);
     if(!Array.isArray(r.data)||!Number.isInteger(r.total)||r.total<0||r.total>5000||r.data.length>50)
      throw Error('The saved brochure prices could not be verified. Load prices again.');
     total=r.total;
     if(start!==revision||!editable(true))return;
     for(const p of r.data){const o=byId.get(p.id);if(valid(p,o))next.set(p.id,p);}
     page++;
    }while((page-1)*50<total);
    saved=next;loaded=true;
    note.textContent=saved.size+' of 40 priced brochure options available. Prices are for the whole run.';
   }catch(error){if(start===revision){saved.clear();note.textContent='Prices could not be loaded. Try loading them again.';}throw error;}
   finally{update();}
  }
  load.onclick=()=>run(loadPrices);
  for(const select of [format,copies])select.onchange=()=>{revision++;update();};
  add.onclick=()=>run(async()=>{
   if(!editable(true))return;
   const o=chosen(),p=o?saved.get(o.id):null,start=revision;
   if(!valid(p,o))throw Error('Choose an available brochure run first.');
   const current=(await api('/api/products/'+o.id)).data;
   if(start!==revision||chosen()?.id!==o.id||!editable(true))return;
   if(!valid(current,o)){
    saved.delete(o.id);update();
    throw Error('This brochure run was archived or its identifying details changed. Review the product before using it.');
   }
   // A price change is shown for review instead of silently adding a different price.
   if(JSON.stringify(current.data)!==JSON.stringify(p.data)){
    saved.set(o.id,current);update();
    throw Error('The saved brochure price or details changed. Review the updated price, then add the run again.');
   }
   const d=current.data,description=[d.name,d.description].filter(Boolean).join('\n');
   if(description.length>1000)throw Error('The brochure description is too long. Shorten it in Products first.');
   onAdd({description,quantity:'1',unit:'Run',unit_price:d.unit_price,vat_rate:d.vat_rate,discount_percent:'0',finish:d.finish,placement:d.placement});
  });
  clear();
  return {clear,update,async open(){root.hidden=false;root.open=true;focusPending=true;await loadPrices();root.scrollIntoView?.({block:'start'});}};
 }
 window.CustomUBrochurePicker=Object.freeze({mount});
})();
