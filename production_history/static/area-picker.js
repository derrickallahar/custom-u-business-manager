'use strict';
(() => {
 const defaultProduct='cc076f06-50f4-5b77-821f-f6ea9a329d76';
 const products=new Map([
  [defaultProduct,{name:'Permanent adhesive vinyl',fixed:false,note:'Includes UV lamination. Matte and Gloss use the same rate. Enter the size of one piece.'}],
  ['aa9cc9d2-4f68-5ae4-b576-da4f4748491d',{name:'Perforated window vinyl',fixed:true,note:'Includes optically clear lamination. Enter the size of one piece.'}]
 ]);
 const messages={NOT_FOUND:'Import the reviewed vinyl product first, then calculate again.',
  AREA_PRODUCT_UNAVAILABLE:'The vinyl product is unavailable or its name, code, unit or rate changed. Review it in Products.',
  INVALID_AREA_REQUEST:'Enter the vinyl dimensions, units, piece count and finish again.',
  INVALID_AREA_OPTIONS:'Choose valid units and a finish for the selected vinyl product.',
  INVALID_AREA_DIMENSIONS:'Enter positive width and height, up to 100,000, with at most three decimal places.',
  INVALID_AREA_QUANTITY:'Enter a whole number of pieces from 1 to 1,000,000.',
  AREA_AMOUNT_BELOW_ONE_CENT:'These measurements produce an amount below one cent. Review the dimensions.',
  AREA_AMOUNT_TOO_LARGE:'This order exceeds the supported line price. Review the dimensions and quantity.',
  AREA_DESCRIPTION_TOO_LONG:'Shorten the vinyl product description or finish in Products, then calculate again.'};
 const cash=cents=>'BSD '+(cents/100).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
 function mount({root,api,run,editable,onAdd}){
  if(!root)return null;
  const get=k=>root.querySelector('[data-area="'+k+'"]');
  const fields=['product_id','width','height','dimension_unit','pieces','finish'];
  let result=null,signature='',revision=0;
  const input=()=>Object.fromEntries(fields.map(k=>[k,get(k).value]));
  get('product_id').replaceChildren(...[...products].map(([id,p])=>new Option(p.name,id)));
  const spec=()=>products.get(get('product_id').value);
  const sameInput=()=>signature===JSON.stringify(input());
  function update(){
   const enabled=editable();
   for(const k of fields)get(k).disabled=!enabled;
   get('finish').disabled=!enabled||spec()?.fixed===true;
   get('calculate').disabled=!enabled;
   get('add').disabled=!enabled||!result||!sameInput();
  }
  function invalidate(){revision++;result=null;signature='';get('price').textContent='';get('detail').textContent='Calculate again after changing dimensions, quantity or finish.';update();}
  function finishOptions(){
   const fixed=spec()?.fixed===true;
   get('finish').replaceChildren(...(fixed?[['Optically clear','Optically clear — included']]:[['','Not specified'],['Matte','Matte'],['Gloss','Gloss']]).map(([v,t])=>new Option(t,v)));
   get('finish-label').textContent=fixed?'Lamination included':'Lamination finish (optional)';
   get('product-note').textContent=spec()?.name==='Perforated window vinyl'?'Digitally printed perforated window vinyl, including optically clear lamination.':'Digitally printed permanent adhesive vinyl, including UV lamination.';
  }
  function clear(){
   revision++;result=null;signature='';get('width').value='';get('height').value='';
   get('dimension_unit').value='in';get('pieces').value='1';get('product_id').value=defaultProduct;finishOptions();
   get('price').textContent='';get('detail').textContent=spec().note;update();
  }
  function show(r,key){
   if(r?.product_id!==get('product_id').value||!r.line||r.line.quantity!=='1'||r.line.unit!=='Job'||
      !Number.isSafeInteger(r.net_cents)||r.net_cents<=0||!Number.isSafeInteger(r.vat_cents)||r.vat_cents<0||
      r.total_cents!==r.net_cents+r.vat_cents||typeof r.rate!=='string'||typeof r.area_sqft!=='string')
    throw Error('The vinyl calculation could not be verified. Calculate again.');
   result=r;signature=key;
   get('detail').textContent=(r.area_approximate?'Approximately ':'')+r.area_sqft+' sq ft total × BSD '+r.rate+'/sq ft. '+
    (spec()?.fixed?'Optically clear lamination included.':r.inputs.finish?r.inputs.finish+' UV lamination.':'UV lamination included; finish not specified.')+
    ' Adds 1 Job; dimensions and piece count are included in the description.';
   get('price').textContent=cash(r.net_cents)+' before VAT + '+cash(r.vat_cents)+' VAT ('+r.line.vat_rate+'%) = '+cash(r.total_cents)+'.';
   update();
  }
  for(const k of fields){get(k).oninput=invalidate;get(k).onchange=invalidate;}
  get('product_id').oninput=get('product_id').onchange=()=>{finishOptions();invalidate();get('detail').textContent=spec()?.note||'Choose a vinyl product.';};
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
  return {update,clear,accepts:id=>products.has(id),open:id=>{if(products.has(id)&&id!==get('product_id').value){get('product_id').value=id;finishOptions();invalidate();get('detail').textContent=spec().note;}root.open=true;get('width').focus();root.scrollIntoView?.({behavior:'smooth',block:'center'});}};
 }
 window.CustomUAreaPicker=Object.freeze({mount,messages});
})();
