/* Live positioning aid. The server-rendered Update preview remains the saved proof. */
(() => {
 'use strict';
 const bound=(v,lo,hi)=>Math.max(lo,Math.min(hi,v)),round=v=>Math.round(v*10)/10;
 function geometry(bw,bh,lw,lh,c){
  let width=Math.max(1,Math.round(bw*c.width/100)),height=Math.max(1,Math.round(width*lh/lw));
  const scale=Math.min(1,bw/width,bh/height);width=Math.max(1,Math.round(width*scale));height=Math.max(1,Math.round(height*scale));
  const angle=c.rotation*Math.PI/180,cos=Math.abs(Math.cos(angle)),sin=Math.abs(Math.sin(angle));let rw=width*cos+height*sin,rh=width*sin+height*cos;
  const rotatedFit=Math.min(1,bw/rw,bh/rh);width*=rotatedFit;height*=rotatedFit;rw*=rotatedFit;rh*=rotatedFit;
  const left=bound(bw*c.x/100-rw/2,0,bw-rw),top=bound(bh*c.y/100-rh/2,0,bh-rh);
  return {width,height,rw,rh,left,top,cx:left+rw/2,cy:top+rh/2,angle};
 }
 function mount({config,onChange,editable}){
  const canvas=document.getElementById('manual-canvas'),wrap=document.getElementById('manual-stage'),note=document.getElementById('manual-note');
  let base=null,art=null,epoch=0,drag=null,shape=null,urls=[];
  const ranges=['x','y','width','rotation'];
  function valid(){return ranges.every(k=>document.getElementById(k+'-number').checkValidity());}
  function sync(){for(const k of ranges){const field=document.getElementById(k+'-number');field.value=document.getElementById(k).value;field.setCustomValidity('');}}
  function change(values){for(const [k,value] of Object.entries(values)){const field=document.getElementById(k);field.value=round(bound(value,Number(field.min),Number(field.max)));}sync();onChange();}
  function revoke(){for(const url of urls)URL.revokeObjectURL(url);urls=[];}
  function clear(){epoch++;base=null;art=null;shape=null;drag=null;revoke();canvas.width=1;canvas.height=1;wrap.hidden=true;note.textContent='Click Update preview once to load the artwork here. Then drag to position, drag the corner to resize, or use the exact controls.';}
  function image(url){return new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(Error('The positioning image could not be loaded. Click Update preview to retry.'));img.src=url;});}
  async function load(baseURL,logo){
   clear();const ticket=epoch;note.textContent='Loading the manual positioning canvas…';
   try{
    const bytes=Uint8Array.from(atob(logo.content_base64),c=>c.charCodeAt(0));const url=URL.createObjectURL(new Blob([bytes],{type:'image/webp'}));urls.push(url);
    const [photo,logoImage]=await Promise.all([image(baseURL),image(url)]);
    if(ticket!==epoch)return;
    const temp=document.createElement('canvas');temp.width=logoImage.naturalWidth;temp.height=logoImage.naturalHeight;const ctx=temp.getContext('2d');ctx.drawImage(logoImage,0,0);
    const data=ctx.getImageData(0,0,temp.width,temp.height).data;let x0=temp.width,y0=temp.height,x1=-1,y1=-1;
    for(let y=0;y<temp.height;y++)for(let x=0;x<temp.width;x++)if(data[(y*temp.width+x)*4+3]){x0=Math.min(x0,x);y0=Math.min(y0,y);x1=Math.max(x1,x);y1=Math.max(y1,y);}
    if(x1<0)throw Error('The artwork is fully transparent.');
    const cropped=document.createElement('canvas');cropped.width=x1-x0+1;cropped.height=y1-y0+1;cropped.getContext('2d').drawImage(temp,x0,y0,cropped.width,cropped.height,0,0,cropped.width,cropped.height);
    base=photo;art=cropped;canvas.width=photo.naturalWidth;canvas.height=photo.naturalHeight;wrap.hidden=false;revoke();draw();
    note.textContent='Drag the artwork to move it. Drag the blue corner to resize. Click elsewhere on the product to place it there. Arrow keys move it; hold Shift for finer steps. Click Update preview to verify before saving.';
   }catch(err){if(ticket===epoch){clear();note.textContent=err.message;}}
  }
  function draw(){
   if(!base||!art)return;
   const c=config(),ctx=canvas.getContext('2d'),bw=canvas.width,bh=canvas.height;shape=geometry(bw,bh,art.width,art.height,c);
   ctx.clearRect(0,0,bw,bh);ctx.drawImage(base,0,0,bw,bh);
   let logo=art;
   if(c.finish!=='colour'){logo=document.createElement('canvas');logo.width=art.width;logo.height=art.height;const tint=logo.getContext('2d');tint.drawImage(art,0,0);tint.globalCompositeOperation='source-in';tint.fillStyle=c.finish==='engraved-dark'?'rgb(65,55,45)':'rgb(220,218,210)';tint.fillRect(0,0,logo.width,logo.height);}
   ctx.save();ctx.translate(shape.cx,shape.cy);ctx.rotate(shape.angle);ctx.drawImage(logo,-shape.width/2,-shape.height/2,shape.width,shape.height);ctx.restore();
   const rect=canvas.getBoundingClientRect(),pixel=bw/(rect.width||bw),size=12*pixel;ctx.lineWidth=2*pixel;ctx.strokeStyle='#006cc5';ctx.setLineDash([5*pixel,4*pixel]);ctx.strokeRect(shape.left,shape.top,shape.rw,shape.rh);ctx.setLineDash([]);ctx.fillStyle='#006cc5';ctx.fillRect(shape.left+shape.rw-size,shape.top+shape.rh-size,size,size);
  }
  function point(ev){const box=canvas.getBoundingClientRect();return {x:(ev.clientX-box.left)*canvas.width/box.width,y:(ev.clientY-box.top)*canvas.height/box.height};}
  canvas.addEventListener('pointerdown',ev=>{
   if(!editable()||!shape||!base||ev.button!==0)return;ev.preventDefault();canvas.focus();const p=point(ev),box=canvas.getBoundingClientRect(),hit=18*canvas.width/box.width,c=config();
   const resize=Math.abs(p.x-(shape.left+shape.rw))<=hit&&Math.abs(p.y-(shape.top+shape.rh))<=hit;
   const inside=p.x>=shape.left&&p.x<=shape.left+shape.rw&&p.y>=shape.top&&p.y<=shape.top+shape.rh;
   if(!resize&&!inside){change({x:p.x/canvas.width*100,y:p.y/canvas.height*100});}
   drag={pointer:ev.pointerId,resize,x:p.x,y:p.y,cx:shape.cx,cy:shape.cy,width:c.width,distance:Math.max(1,Math.hypot(p.x-shape.cx,p.y-shape.cy))};canvas.setPointerCapture?.(ev.pointerId);
  });
  canvas.addEventListener('pointermove',ev=>{
   if(!drag||drag.pointer!==ev.pointerId||!editable())return;ev.preventDefault();const p=point(ev);
   if(drag.resize)change({width:drag.width*Math.hypot(p.x-drag.cx,p.y-drag.cy)/drag.distance});
   else change({x:(drag.cx+p.x-drag.x)/canvas.width*100,y:(drag.cy+p.y-drag.y)/canvas.height*100});
  });
  function stop(ev){if(drag?.pointer===ev.pointerId){canvas.releasePointerCapture?.(ev.pointerId);drag=null;}}
  canvas.addEventListener('pointerup',stop);canvas.addEventListener('pointercancel',stop);canvas.addEventListener('lostpointercapture',()=>{drag=null;});
  canvas.addEventListener('keydown',ev=>{if(!editable()||!base||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(ev.key))return;ev.preventDefault();const c=config(),step=ev.shiftKey?0.1:1;change({x:c.x+(ev.key==='ArrowRight'?step:ev.key==='ArrowLeft'?-step:0),y:c.y+(ev.key==='ArrowDown'?step:ev.key==='ArrowUp'?-step:0)});});
  for(const k of ranges){const field=document.getElementById(k+'-number');field.addEventListener('input',()=>{const value=field.valueAsNumber,slider=document.getElementById(k);if(!Number.isFinite(value)||value<Number(slider.min)||value>Number(slider.max)){field.setCustomValidity('Enter a value from '+slider.min+' to '+slider.max+'.');onChange();return;}field.setCustomValidity('');slider.value=round(value);onChange();});field.addEventListener('change',()=>{if(valid())sync();});}
  window.addEventListener('resize',draw);sync();
  return {load,clear,draw,sync,valid};
 }
 window.CustomUMockupEditor={mount,geometry};
})();
