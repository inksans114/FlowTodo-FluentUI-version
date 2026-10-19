const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
export async function bridgeExchange(env,id,envelope,kind,timeout){
 const now=Date.now(),q=(sql,...args)=>env.DB.prepare(sql).bind(...args);
 const count=await q('SELECT count(*) AS n FROM storage_bridge_jobs WHERE expires>?',now).first();
 if(count.n>=64)throw new Error('storage_busy');
 await q("INSERT INTO storage_bridge_jobs(id,payload,state,kind,created,expires) VALUES(?,?,'queued',?,?,?)",id,JSON.stringify(envelope),kind,now,now+timeout).run();
 try{
  while(Date.now()<now+timeout){
   const row=await q('SELECT response FROM storage_bridge_jobs WHERE id=?',id).first();
   if(row?.response)return new Response(row.response,{headers:{'Content-Type':'application/json'}});
   await pause(500);
  }
  throw new Error('storage_connect');
 }finally{await q('DELETE FROM storage_bridge_jobs WHERE id=?',id).run();}
}
export async function bridgeApi(request,env,json){
 const path=new URL(request.url).pathname;
 if(!['/api/storage/bridge/poll','/api/storage/bridge/result'].includes(path)||request.method!=='POST')return json({error:'未找到此功能。'},404);
 if(!env.STORAGE_KEY)return json({error:'连接尚未配置。'},503);
 const raw=await request.text();if(raw.length>2800000)return json({error:'请求过大。'},413);
 try{
  const encoder=new TextEncoder(),key=await crypto.subtle.importKey('raw',Uint8Array.from(env.STORAGE_KEY.match(/.{2}/g),h=>parseInt(h,16)),{name:'HMAC',hash:'SHA-256'},false,['verify']);
  const signature=request.headers.get('X-FlowTodo-Bridge')||'';
  if(!/^[a-f0-9]{64}$/.test(signature)||!await crypto.subtle.verify('HMAC',key,Uint8Array.from(signature.match(/.{2}/g),h=>parseInt(h,16)),encoder.encode('flowtodo-storage-bridge-v1\n'+path+'\n'+raw)))return json({error:'身份验证失败。'},403);
  const body=JSON.parse(raw),now=Date.now(),q=(sql,...args)=>env.DB.prepare(sql).bind(...args);
  if(!Number.isFinite(body.at)||Math.abs(now-body.at)>60000||!/^[a-f0-9-]{36}$/.test(body.nonce))return json({error:'请求已失效。'},403);
  await env.DB.batch([q('DELETE FROM storage_bridge_nonces WHERE expires<?',now),q('INSERT INTO storage_bridge_nonces VALUES(?,?)',body.nonce,now+120000),q('DELETE FROM storage_bridge_jobs WHERE expires<?',now)]);
  if(path.endsWith('/result')){
   if(!/^[a-f0-9-]{36}$/.test(body.id)||typeof body.envelope?.data!=='string'||typeof body.envelope?.nonce!=='string')return json({error:'响应格式无效。'},400);
   await q("UPDATE storage_bridge_jobs SET response=?,state='complete' WHERE id=? AND state='claimed'",JSON.stringify(body.envelope),body.id).run();return json({ok:true});
  }
  if(!['records','ai'].includes(body.kind))return json({error:'队列无效。'},400);
  for(let i=0;i<20;i++){
   const job=await q("UPDATE storage_bridge_jobs SET state='claimed' WHERE id=(SELECT id FROM storage_bridge_jobs WHERE state='queued' AND kind=? AND expires>? ORDER BY created LIMIT 1) AND state='queued' RETURNING id,payload",body.kind,Date.now()).first();
   if(job)return json({id:job.id,envelope:JSON.parse(job.payload)});
   await pause(1000);
  }
  return json({idle:true});
 }catch{return json({error:'连接请求暂时无法处理。'},503);}
}
