'use strict';
(() => {
 const productId='cc076f06-50f4-5b77-821f-f6ea9a329d76';
 const messages={NOT_FOUND:'Import the reviewed vinyl product first, then calculate again.',
  AREA_PRODUCT_UNAVAILABLE:'The vinyl product is unavailable or its name, code, unit or rate changed. Review it in Products.',
  INVALID_AREA_REQUEST:'Enter the vinyl dimensions, units, piece count and finish again.',
  INVALID_AREA_OPTIONS:'Choose inches or feet and an optional Matte or Gloss finish.',
  INVALID_AREA_DIMENSIONS:'Enter positive width and height, up to 100,000, with at most three decimal places.',
  INVALID_AREA_QUANTITY:'Enter a whole number of pieces from 1 to 1,000,000.',
  AREA_AMOUNT_BELOW_ONE_CENT:'These measurements produce an amount below one cent. Review the dimensions.',
  AREA_AMOUNT_TOO_LARGE:'This order exceeds the supported line price. Review the dimensions and quantity.',
  AREA_DESCRIPTION_TOO_LONG:'Shorten the vinyl product description or finish in Products, then calculate again.'};
 const cash=cents=>'BSD '+(cents/100).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
 function mount({root,api,run,editable,onAdd}){
  if(!root)return null;
  const get=k=>root.querySelector('[data-area="'+k+'"]');
  const fields=['width','height','dimension_unit','pieces','finish'];
  let result=null,signature='',revision=0;
  const input=()=>Object.fromEntries([['product_id',productId],...fields.map(k=>[k,get(k).value])]);
  const sameInput=()=>signature===JSON.stringify(input());
  function update(){
   const enabled=editable();
   for(const k of fields)get(k).disabled=!enabled;
   get('calculate').disabled=!enabled;
   get('add').disabled=!enabled||!result||!sameInput();
  }
  function invalidate(){revision++;result=null;signature='';get('price').textContent='';get('detail').textContent='Calculate again after changing dimensions, quantity or finish.';update();}
  function clear(){
   revision++;result=null;signature='';get('width').value='';get('height').value='';
   get('dimension_unit').value='in';get('pieces').value='1';get('finish').value='';
   get('price').textContent='';get('detail').textContent='Includes UV lamination. Matte and Gloss use the same rate. Enter the size of one piece.';update();
  }
  function show(r,key){
   if(r?.product_id!==productId||!r.line||r.line.quantity!=='1'||r.line.unit!=='Job'||
      !Number.isSafeInteger(r.net_cents)||r.net_cents<=0||!Number.isSafeInteger(r.vat_cents)||r.vat_cents<0||
      r.total_cents!==r.net_cents+r.vat_cents||typeof r.rate!=='string'||typeof r.area_sqft!=='string')
    throw Error('The vinyl calculation could not be verified. Calculate again.');
   result=r;signature=key;
   get('detail').textContent=(r.area_approximate?'Approximately ':'')+r.area_sqft+' sq ft total × BSD '+r.rate+'/sq ft. '+
    (r.inputs.finish?r.inputs.finish+' UV lamination.':'UV lamination included; finish not specified.')+
    ' Adds 1 Job; dimensions and piece count are included in the description.';
   get('price').textContent=cash(r.net_cents)+' before VAT + '+cash(r.vat_cents)+' VAT ('+r.line.vat_rate+'%) = '+cash(r.total_cents)+'.';
   update();
  }
  for(const k of fields){get(k).oninput=invalidate;get(k).onchange=invalidate;}
  get('calculate').onclick=()=>run(async()=>{
   if(!editable(true))return;
   const body=input(),key=JSON.stringify(body),start=++revision;
   result=null;signature='';get('price').textContent='';get('detail').textContent='Calculating from the saved square-foot rate…';
   try{
    const r=await api('/api/products/area-price',body);
    if(start!==revision||key!==JSON.stringify(input()))return;
    show(r,key);
   }catch(error){if(start===revision){result=null;get('detail').textContent=error.message;}throw error;}
  });
  get('add').onclick=()=>run(async()=>{
   if(!editable(true)||!result||!sameInput())return;
   const previous=result,body=input(),key=JSON.stringify(body),start=revision;
   try{
    const current=await api('/api/products/area-price',body);
    if(start!==revision||key!==JSON.stringify(input()))return;
    show(current,key);
    if(JSON.stringify(current)!==JSON.stringify(previous)){
     get('detail').textContent+=' The saved product changed. Review the updated result, then add it again.';
     throw Error('The vinyl rate or product details changed. Review the updated calculation, then add the item again.');
    }
    onAdd(current.line);
    result=null;signature='';get('detail').textContent+=' Added to the document. Calculate again to add another size.';
   }catch(error){if(start===revision&&result===previous){result=null;signature='';get('price').textContent='';}throw error;}
   finally{update();}
  });
  clear();
  return {update,clear,accepts:id=>id===productId,open:()=>{root.open=true;get('width').focus();root.scrollIntoView?.({behavior:'smooth',block:'center'});}};
 }
 window.CustomUAreaPicker=Object.freeze({mount,messages});
})();
