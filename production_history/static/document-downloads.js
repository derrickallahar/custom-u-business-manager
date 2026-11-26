'use strict';
window.CustomUDocuments={
 async download(path,fallback='CustomU_Document.pdf'){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),60000);
  try{
   const response=await fetch(path,{credentials:'same-origin',cache:'no-store',signal:controller.signal});
   if(!response.ok)throw Error(response.status===401||response.status===403?'Sign in with document access before downloading.':'The PDF could not be downloaded. Try again.');
   if(!(response.headers.get('Content-Type')||'').startsWith('application/pdf'))throw Error('The server did not return a PDF.');
   const blob=await response.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');
   const filename=(response.headers.get('Content-Disposition')||'').match(/filename="([A-Za-z0-9_.-]+\.pdf)"/);
   a.href=url;a.download=filename?filename[1]:fallback;document.body.append(a);a.click();a.remove();
   setTimeout(()=>URL.revokeObjectURL(url),60000);
  }catch(e){if(e.name==='AbortError')throw Error('The PDF download timed out. Please try again.');throw e;}finally{clearTimeout(timer);}
 }
};
