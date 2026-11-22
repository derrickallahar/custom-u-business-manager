/* Manual preview canvas; the server-rendered preview remains the saved proof. */
(() => {
 'use strict';
 const bound=(v,lo,hi)=>Math.max(lo,Math.min(hi,v)),round=(v,d=1)=>Math.round(v*10**d)/10**d;
 function geometry(bw,bh,lw,lh,c){
  const angle=c.rotation*Math.PI/180,cos=Math.abs(Math.cos(angle)),sin=Math.abs(Math.sin(angle));
  let width,height,left,top,rw,rh,ref=null,error='';
  if(c.scale){
   const s=c.scale;ref={left:bw*s.left/100,top:bh*s.top/100,width:bw*(s.right-s.left)/100,height:bh*(s.bottom-s.top)/100};
   const ppi=ref.width/s.reference_width;width=s.print_width*ppi;height=width*lh/lw;rw=width*cos+height*sin;rh=width*sin+height*cos;
   if(Math.min(ref.width,ref.height)<8||Math.abs(ppi/(ref.height/s.reference_height)-1)>.01)error='Mark the reference area again to match the item dimensions.';
   else if(Math.min(width,height)<1)error='The print is too small to show on this photo.';
   else if(rw>ref.width+1e-6||rh>ref.height+1e-6)error='This print size and rotation do not fit in the marked area. Reduce the print size or check the reference area.';
   left=bound(bw*c.x/100-rw/2,ref.left,Math.max(ref.left,ref.left+ref.width-rw));top=bound(bh*c.y/100-rh/2,ref.top,Math.max(ref.top,ref.top+ref.height-rh));
  }else{
   width=Math.max(1,Math.round(bw*c.width/100));height=Math.max(1,Math.round(width*lh/lw));
   const scale=Math.min(1,bw/width,bh/height);width=Math.max(1,Math.round(width*scale));height=Math.max(1,Math.round(height*scale));rw=width*cos+height*sin;rh=width*sin+height*cos;
   const fit=Math.min(1,bw/rw,bh/rh);width*=fit;height*=fit;rw*=fit;rh*=fit;left=bound(bw*c.x/100-rw/2,0,bw-rw);top=bound(bh*c.y/100-rh/2,0,bh-rh);
  }
  return {width,height,rw,rh,left,top,cx:left+rw/2,cy:top+rh/2,angle,ref,error};
 }
 function mount({config,onChange,editable,onReady=()=>{}}){
  const $=id=>document.getElementById(id),canvas=$('manual-canvas'),wrap=$('manual-stage'),note=$('manual-note');
  const ranges=['x','y','width','rotation'];let base=null,art=null,epoch=0,drag=null,shape=null,urls=[],scale=null,marking=false,selection=null,anchor=null,markError='';
  const enabled=()=>$('measure-enabled').checked;
  function scaleConfig(){return enabled()&&scale?{...scale}:null;}
  function fieldValid(id){return $(id).checkValidity()&&Number.isFinite($(id).valueAsNumber);}
  function valid(){
   if(!ranges.every(k=>$(k+'-number').checkValidity()))return false;
   if(!enabled())return true;
   return !!(base&&art&&scale&&!marking&&['reference-width','reference-height','print-width-in','print-height-in'].every(fieldValid)&&!geometry(canvas.width,canvas.height,art.width,art.height,config()).error);
  }
  function controls(){
   $('measure-enabled').disabled=!base||!editable();$('measurement-fields').hidden=!enabled();$('print-dimensions').hidden=!enabled();$('mark-reference').disabled=!base||!editable()||marking;
   $('mark-reference').textContent=marking?'Marking area — use the photo below':scale?'Mark area again':'Mark area on photo';
   $('mark-reference').setAttribute('aria-pressed',String(marking));$('cancel-reference').hidden=!marking;$('cancel-reference').disabled=!editable();wrap.dataset.marking=String(marking);
   for(const id of ['reference-width','reference-height'])$(id).disabled=!editable()||!enabled()||marking;
   for(const id of ['print-width-in','print-height-in'])$(id).disabled=!editable()||!enabled()||!scale||marking;
   $('marking-note').hidden=!marking;
   $('marking-note').textContent=markError||(anchor?'First corner selected. Click the opposite corner to finish. Escape cancels.':'Marking is on. Click two opposite corners of the item area, or drag between them. The green box follows your entered proportions. Escape cancels.');
   canvas.setAttribute('aria-label',marking?'Mark reference area: click two opposite corners or drag a rectangle. Escape cancels.':'Move and resize the logo on the product. Arrow keys move it; Shift uses smaller steps.');
  }
  function sync(){for(const k of ranges){const field=$(k+'-number');field.value=$(k).value;field.setCustomValidity('');}}
  function dimensions(){if(!scale||!art)return;$('print-width-in').value=scale.print_width;$('print-height-in').value=round(scale.print_width*art.height/art.width,3);}
  function percentWidth(value){if(!enabled()||!scale||!base)return;scale.print_width=round(bound(Number(value)*scale.reference_width/(scale.right-scale.left),.001,2000),3);dimensions();}
  function change(values){for(const [k,v] of Object.entries(values)){$(k).value=round(bound(v,Number($(k).min),Number($(k).max)));if(k==='width')percentWidth(v);}sync();onChange();}
  function revoke(){for(const url of urls)URL.revokeObjectURL(url);urls=[];}
  function clear({preserveScale=false}={}){
   epoch++;base=null;art=null;shape=null;drag=null;marking=false;selection=null;anchor=null;markError='';revoke();canvas.width=1;canvas.height=1;wrap.hidden=true;
   if(!preserveScale){scale=null;$('measure-enabled').checked=false;for(const id of ['reference-width','reference-height','print-width-in','print-height-in'])$(id).value='';$('measure-note').textContent='';$('print-size-note').textContent='';}
   note.textContent='Click Update preview once to load the artwork here. Then drag to position, drag the corner to resize, or use the exact controls.';controls();
  }
  function restore(value){scale=value?{...value}:null;$('measure-enabled').checked=!!value;if(value){$('reference-width').value=value.reference_width;$('reference-height').value=value.reference_height;$('print-width-in').value=value.print_width;}controls();}
  function image(url){return new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(Error('The positioning image could not be loaded. Click Update preview to retry.'));img.src=url;});}
  async function load(baseURL,logo){
   clear({preserveScale:true});const ticket=epoch;note.textContent='Loading the manual positioning canvas…';
   try{
    const bytes=Uint8Array.from(atob(logo.content_base64),c=>c.charCodeAt(0)),url=URL.createObjectURL(new Blob([bytes],{type:'image/webp'}));urls.push(url);
    const [photo,logoImage]=await Promise.all([image(baseURL),image(url)]);if(ticket!==epoch)return;
    const temp=document.createElement('canvas');temp.width=logoImage.naturalWidth;temp.height=logoImage.naturalHeight;const ctx=temp.getContext('2d');ctx.drawImage(logoImage,0,0);
    const data=ctx.getImageData(0,0,temp.width,temp.height).data;let x0=temp.width,y0=temp.height,x1=-1,y1=-1;
    for(let y=0;y<temp.height;y++)for(let x=0;x<temp.width;x++)if(data[(y*temp.width+x)*4+3]){x0=Math.min(x0,x);y0=Math.min(y0,y);x1=Math.max(x1,x);y1=Math.max(y1,y);}
    if(x1<0)throw Error('The artwork is fully transparent.');
    const cropped=document.createElement('canvas');cropped.width=x1-x0+1;cropped.height=y1-y0+1;cropped.getContext('2d').drawImage(temp,x0,y0,cropped.width,cropped.height,0,0,cropped.width,cropped.height);
    base=photo;art=cropped;canvas.width=photo.naturalWidth;canvas.height=photo.naturalHeight;wrap.hidden=false;revoke();dimensions();draw();controls();onReady();
    note.textContent='Drag the artwork to move it. Drag the blue corner to resize. Click elsewhere to place it. Arrow keys move it; Shift gives finer steps. Update preview before saving.';
   }catch(err){if(ticket===epoch){clear();note.textContent=err.message;}}
  }
  function draw(){
   if(!base||!art)return;const c=config(),ctx=canvas.getContext('2d'),bw=canvas.width,bh=canvas.height;shape=geometry(bw,bh,art.width,art.height,c);
   ctx.clearRect(0,0,bw,bh);ctx.drawImage(base,0,0,bw,bh);let logo=art;
   if(c.finish!=='colour'){logo=document.createElement('canvas');logo.width=art.width;logo.height=art.height;const tint=logo.getContext('2d');tint.drawImage(art,0,0);tint.globalCompositeOperation='source-in';tint.fillStyle=c.finish==='engraved-dark'?'rgb(65,55,45)':'rgb(220,218,210)';tint.fillRect(0,0,logo.width,logo.height);}
   if(!shape.error){ctx.save();ctx.translate(shape.cx,shape.cy);ctx.rotate(shape.angle);ctx.drawImage(logo,-shape.width/2,-shape.height/2,shape.width,shape.height);ctx.restore();}
   const rect=canvas.getBoundingClientRect(),pixel=bw/(rect.width||bw),size=12*pixel;ctx.lineWidth=2*pixel;ctx.setLineDash([5*pixel,4*pixel]);
   if(!shape.error){ctx.strokeStyle='#006cc5';ctx.strokeRect(shape.left,shape.top,shape.rw,shape.rh);ctx.fillStyle='#006cc5';ctx.fillRect(shape.left+shape.rw-size,shape.top+shape.rh-size,size,size);}
   const ref=selection||shape.ref;if(ref){ctx.strokeStyle='#148346';ctx.strokeRect(ref.left,ref.top,ref.width,ref.height);}ctx.setLineDash([]);
   if(marking&&anchor){ctx.fillStyle='#148346';ctx.fillRect(anchor.x-size/2,anchor.y-size/2,size,size);}
   if(enabled()){
    $('measure-note').textContent=marking?'Marking is on — select two corners on the working photo.':!scale?'Enter the area dimensions, then click Mark area on photo. Print sizing becomes available after marking.':`Area marked: ${scale.reference_width} × ${scale.reference_height} inches. Set the print size below the photo.`;
    $('print-size-note').textContent=!scale?'Mark the item area first to enable these fields.':!['print-width-in','print-height-in'].every(fieldValid)?'Enter a positive print size, using up to three decimal places.':shape.error||`Print: ${scale.print_width} × ${round(scale.print_width*art.height/art.width,3)} inches. Working photo updated. Click Update preview before saving.`;
    // Keep geometry errors visible above the photo as well as beside the size fields.
    if(scale&&!marking&&shape.error)$('measure-note').textContent=shape.error;
   }
   controls();
  }
  function point(ev){const b=canvas.getBoundingClientRect();return {x:bound((ev.clientX-b.left)*canvas.width/b.width,0,canvas.width),y:bound((ev.clientY-b.top)*canvas.height/b.height,0,canvas.height)};}
  function markBox(p,origin=drag){const ratio=$('reference-width').valueAsNumber/$('reference-height').valueAsNumber,w=Math.min(Math.abs(p.x-origin.x),Math.abs(p.y-origin.y)*ratio),h=w/ratio;return {left:p.x<origin.x?origin.x-w:origin.x,top:p.y<origin.y?origin.y-h:origin.y,width:w,height:h};}
  canvas.addEventListener('pointerdown',ev=>{
   if(!editable()||!shape||!base||ev.button!==0)return;ev.preventDefault();canvas.focus();const p=point(ev);
   if(marking){drag={pointer:ev.pointerId,mark:true,x:anchor?.x??p.x,y:anchor?.y??p.y,second:!!anchor};markError='';selection=null;canvas.setPointerCapture?.(ev.pointerId);return;}
   if(shape.error)return;
   const box=canvas.getBoundingClientRect(),hit=18*canvas.width/box.width,c=config(),resize=Math.abs(p.x-(shape.left+shape.rw))<=hit&&Math.abs(p.y-(shape.top+shape.rh))<=hit,inside=p.x>=shape.left&&p.x<=shape.left+shape.rw&&p.y>=shape.top&&p.y<=shape.top+shape.rh;
   if(!resize&&!inside)change({x:p.x/canvas.width*100,y:p.y/canvas.height*100});
   drag={pointer:ev.pointerId,resize,x:p.x,y:p.y,cx:shape.cx,cy:shape.cy,width:c.width,inch:scale?.print_width,distance:Math.max(1,Math.hypot(p.x-shape.cx,p.y-shape.cy))};canvas.setPointerCapture?.(ev.pointerId);
  });
  canvas.addEventListener('pointermove',ev=>{
   if(!editable())return;if(marking&&anchor&&!drag){selection=markBox(point(ev),anchor);draw();return;}if(!drag||drag.pointer!==ev.pointerId)return;ev.preventDefault();const p=point(ev);
   if(drag.mark){selection=markBox(p);draw();return;}
   if(drag.resize){const factor=Math.hypot(p.x-drag.cx,p.y-drag.cy)/drag.distance;if(enabled()&&scale){scale.print_width=round(bound(drag.inch*factor,.001,2000),3);dimensions();$('width').value=round(bound(scale.print_width*(scale.right-scale.left)/scale.reference_width,1,100));sync();onChange();}else change({width:drag.width*factor});}
   else change({x:(drag.cx+p.x-drag.x)/canvas.width*100,y:(drag.cy+p.y-drag.y)/canvas.height*100});
  });
  function cancelMark(){marking=false;anchor=null;selection=null;drag=null;markError='';onChange();}
  function stop(ev){
   if(drag?.pointer!==ev.pointerId)return;
   if(drag.mark&&ev.type==='pointerup'){
    selection=markBox(point(ev));
    if(Math.min(selection.width,selection.height)>=8){
     const oldWidth=scale?.print_width;
     scale={unit:'in',reference_width:$('reference-width').valueAsNumber,reference_height:$('reference-height').valueAsNumber,left:round(selection.left/canvas.width*100,4),top:round(selection.top/canvas.height*100,4),right:round((selection.left+selection.width)/canvas.width*100,4),bottom:round((selection.top+selection.height)/canvas.height*100,4),print_width:oldWidth??round($('reference-width').valueAsNumber/4,3)};
     dimensions();marking=false;anchor=null;markError='';$('width').value=round(bound(scale.print_width*(scale.right-scale.left)/scale.reference_width,1,100));sync();
    }else{
     anchor={x:drag.x,y:drag.y};markError=drag.second?'That area is too small. Click a farther opposite corner, or cancel and start again.':'';
    }
   }
   drag=null;selection=null;canvas.releasePointerCapture?.(ev.pointerId);onChange();
  }
  canvas.addEventListener('pointerup',stop);canvas.addEventListener('pointercancel',stop);canvas.addEventListener('lostpointercapture',()=>{drag=null;selection=null;draw();});
  canvas.addEventListener('keydown',ev=>{if(marking&&ev.key==='Escape'){ev.preventDefault();cancelMark();return;}if(!editable()||!base||marking||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(ev.key))return;ev.preventDefault();const c=config(),step=ev.shiftKey ? 0.1 : 1;change({x:c.x+(ev.key==='ArrowRight'?step:ev.key==='ArrowLeft'?-step:0),y:c.y+(ev.key==='ArrowDown'?step:ev.key==='ArrowUp'?-step:0)});});
  for(const k of ranges){const field=$(k+'-number');field.addEventListener('input',()=>{const value=field.valueAsNumber,slider=$(k);if(!Number.isFinite(value)||value<Number(slider.min)||value>Number(slider.max)){field.setCustomValidity('Enter a value from '+slider.min+' to '+slider.max+'.');onChange();return;}field.setCustomValidity('');slider.value=round(value);if(k==='width')percentWidth(value);onChange();});field.addEventListener('change',()=>{if(valid())sync();});}
  $('measure-enabled').addEventListener('change',()=>{cancelMark();controls();});
  for(const id of ['reference-width','reference-height'])$(id).addEventListener('input',()=>{scale=null;marking=false;anchor=null;selection=null;markError='';$('print-width-in').value='';$('print-height-in').value='';onChange();});
  $('mark-reference').addEventListener('click',()=>{if(!['reference-width','reference-height'].every(fieldValid)){$('measure-note').textContent='Enter a positive width and height in inches first.';return;}marking=true;anchor=null;selection=null;markError='';onChange();wrap.scrollIntoView?.({behavior:'smooth',block:'start'});canvas.focus({preventScroll:true});});
  $('cancel-reference').addEventListener('click',cancelMark);
  for(const id of ['print-width-in','print-height-in'])$(id).addEventListener('input',()=>{if(scale&&art&&fieldValid(id)){scale.print_width=round(bound($(id).valueAsNumber*(id==='print-height-in'?art.width/art.height:1),.001,2000),3);if(id==='print-width-in')$('print-height-in').value=round(scale.print_width*art.height/art.width,3);else $('print-width-in').value=scale.print_width;$('width').value=round(bound(scale.print_width*(scale.right-scale.left)/scale.reference_width,1,100));sync();}onChange();});
  window.addEventListener('resize',draw);sync();controls();
  return {load,clear,draw,sync,valid,controls,restore,scaleConfig,percentageChanged:k=>{if(k==='width')percentWidth($('width').value);}};
 }
 window.CustomUMockupEditor={mount,geometry};
})();
