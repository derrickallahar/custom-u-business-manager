'use strict';
(() => {
 function mount({root,api,run,editable,onAdd}){
  if(!root)return null;
  let product=null,result=null,revision=0,focusPending=false;
  const fields={};
  const title=document.createElement('h3'),help=document.createElement('p'),inputs=document.createElement('div'),message=document.createElement('p');
  inputs.className='grid';message.setAttribute('role','status');
  root.append(title,help,inputs);
  function field(key,label,options){
   const lab=document.createElement('label');lab.textContent=label;
   const input=document.createElement(options?'select':'input');
   input.dataset.pricing=key;
   if(options)for(const [value,text] of options)input.append(new Option(text,value));
   else{input.type='number';input.min='0.001';input.max='100000';input.step='0.001';}
   fields[key]=input;lab.append(input);inputs.append(lab);
   input.oninput=input.onchange=()=>{revision++;result=null;message.textContent='Calculate again after changing the inputs.';update();};
   return input;
  }
  field('width','Width of one piece');field('height','Height of one piece');
  field('dimension_unit','Dimension units',[['in','Inches'],['ft','Feet']]);
  field('option','Priced option',[]);
  field('pieces','Quantity');fields.pieces.min='1';fields.pieces.max='1000000';fields.pieces.step='1';
  const calculate=document.createElement('button'),add=document.createElement('button'),close=document.createElement('button');
  for(const [b,text] of [[calculate,'Calculate price'],[add,'Add priced item'],[close,'Close pricing']]){b.type='button';b.textContent=text;root.append(b);}
  root.append(message);root.hidden=true;
  function update(){for(const i of [...Object.values(fields),calculate,close])i.disabled=!editable();add.disabled=!editable()||!result;if(editable()&&focusPending)queueMicrotask(()=>{const field=product?.data.pricing.mode==='area'?fields.width:product?.data.pricing.mode==='grid'?fields.option:fields.pieces;if(focusPending&&product&&editable()&&!field.matches(':disabled')){focusPending=false;field.focus();}});}
  function clear(){revision++;focusPending=false;product=null;result=null;root.hidden=true;title.textContent='';help.textContent='';message.textContent='';fields.option.replaceChildren();for(const k of ['width','height','pieces'])fields[k].value='';update();}
  function open(p){
   clear();if(!p?.active||!p.data?.pricing||!editable(true))throw Error('This product is not ready for pricing.');
   product=p;root.hidden=false;title.textContent=p.data.name;
   const mode=p.data.pricing.mode;
   help.textContent='Prices are before VAT. The complete calculated order is added as 1 Job; dimensions or copy counts are retained in the description. Edit those inputs here, then calculate.';
   for(const k of ['width','height','dimension_unit'])fields[k].closest('label').hidden=mode!=='area';
   fields.option.closest('label').hidden=mode!=='grid';
   fields.dimension_unit.value='in';fields.pieces.value='1';
   if(mode==='grid')for(const o of p.data.pricing.options.filter(o=>Number(o.price)>0))fields.option.append(new Option(o.label+' · '+o.copies+' copies · BSD '+o.price+' per run',o.label));
   fields.pieces.closest('label').firstChild.textContent=mode==='grid'?'Number of runs':mode==='area'?'Number of pieces':'Quantity ('+p.data.unit+')';
   message.textContent='Enter the order details and calculate the price.';focusPending=true;update();root.scrollIntoView?.({block:'nearest'});
  }
  function body(){const mode=product.data.pricing.mode;return {product_id:product.id,version:product.version,width:mode==='area'?fields.width.value:'',height:mode==='area'?fields.height.value:'',dimension_unit:mode==='area'?fields.dimension_unit.value:'',pieces:fields.pieces.value,option:mode==='grid'?fields.option.value:''};}
  async function price(){
   const start=revision,p=product,b=body(),current=(await api('/api/products/'+p.id)).data;
   if(start!==revision||product!==p)return null;
   if(current.version!==p.version||!current.active){result=null;message.textContent='Product pricing changed. Search for this product again to review its current settings.';throw Error(message.textContent);}
   const r=await api('/api/products/configured-price',b);
   if(start!==revision||product!==p||!editable(true))return null;
   if(r?.product_id!==p.id||r.version!==p.version||!Number.isSafeInteger(r.net_cents)||r.net_cents<=0||!Number.isSafeInteger(r.vat_cents)||r.vat_cents<0||r.total_cents!==r.net_cents+r.vat_cents||r.line?.quantity!=='1'||r.line?.unit!=='Job'||Number(r.line.unit_price)*100!==r.net_cents&&Math.round(Number(r.line.unit_price)*100)!==r.net_cents)throw Error('The price could not be verified. Calculate again.');
   return r;
  }
  const show=r=>{result=r;message.textContent='BSD '+(r.net_cents/100).toFixed(2)+' before VAT + BSD '+(r.vat_cents/100).toFixed(2)+' VAT = BSD '+(r.total_cents/100).toFixed(2)+'.';update();};
  calculate.onclick=()=>run(async()=>{if(!product||!editable(true))return;result=null;const r=await price();if(r)show(r);});
  add.onclick=()=>run(async()=>{if(!result||!product||!editable(true))return;const previous=JSON.stringify(result),r=await price();if(!r)return;if(JSON.stringify(r)!==previous){show(r);message.textContent+=' Price changed; review it and click Add again.';return;}onAdd(r.line);clear();});
  close.onclick=clear;
  return {open,clear,update};
 }
 window.CustomUPricingPicker={mount,messages:{
   PRICING_CHANGED:'The saved price changed. Search for the product again and review its new price.',
   PRICING_UNAVAILABLE:'This product or option has no active price. Review its pricing in Products.',
   INVALID_PRICING_REQUEST:'Review the selected product and pricing inputs, then calculate again.',
   INVALID_PRICING_QUANTITY:'Enter a whole-number quantity from 1 to 1,000,000.',
   INVALID_PRICING_DIMENSIONS:'Enter positive width and height, with at most three decimals, up to 100,000.',
   INVALID_PRICING_TOTAL:'The calculated price is below one cent or exceeds BSD 1,000,000. Review the quantity and dimensions.',
   PRICING_DESCRIPTION_TOO_LONG:'Shorten the product description in Products, then select it again.'
  }};
})();
