import {bridgeExchange} from './bridge.js';
const encode=b=>{const bytes=new Uint8Array(b);let s='';for(let i=0;i<bytes.length;i+=32768)s+=String.fromCharCode(...bytes.subarray(i,i+32768));return btoa(s);};
const decode=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
export async function storageCall(env,user,path,method='GET',body={}){
 const key=await crypto.subtle.importKey('raw',Uint8Array.from(env.STORAGE_KEY.match(/.{2}/g),h=>parseInt(h,16)),{name:'AES-GCM'},false,['encrypt','decrypt']);
 const id=crypto.randomUUID(),at=Date.now(),nonce=crypto.getRandomValues(new Uint8Array(12)),text=new TextEncoder();
 const plaintext=text.encode(JSON.stringify({id,at,user:{id:user.id,plan:user.plan,role:user.role||'user'},path,method,body}));
 const data=await crypto.subtle.encrypt({name:'AES-GCM',iv:nonce,additionalData:text.encode('flowtodo-storage-request-v1')},key,plaintext);
 let response;
 const envelopeIn={nonce:encode(nonce),data:encode(data)},ai=path.startsWith('/api/ai/');
 try{response=env.STORAGE_MODE==='reverse'?await bridgeExchange(env,id,envelopeIn,ai?'ai':'records',ai?280000:15000):await (env.STORAGE_FETCH||fetch)(env.STORAGE_ORIGIN,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(envelopeIn),signal:AbortSignal.timeout(ai?280000:18000),redirect:'manual'});}
 catch(error){console.warn('FLOWTODO_STORAGE_NETWORK',error.name,String(error.message||'').slice(0,180));const issue=new Error('storage_connect');issue.networkDetail=String(error.message||'').slice(0,180);throw issue;}
 if(!response.ok)throw new Error('storage_http_'+response.status);
 const envelope=await response.json();
 const decrypted=await crypto.subtle.decrypt({name:'AES-GCM',iv:decode(envelope.nonce),additionalData:text.encode('flowtodo-storage-response-v1')},key,decode(envelope.data));
 const result=JSON.parse(new TextDecoder().decode(decrypted));
 if(result.id!==id||Math.abs(Date.now()-result.at)>300000)throw new Error('storage_response');
 return result;
}
