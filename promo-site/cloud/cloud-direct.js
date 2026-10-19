import { sign } from './ai-direct.js';
const decode=s=>Uint8Array.from(atob(s.replaceAll('-','+').replaceAll('_','/')),c=>c.charCodeAt(0));
export async function directCloudApi({path,method,body,session,q,now,json,env,fail,limit}) {
 if(!env.CLOUD_DIRECT_ENABLED)return null;
 if(path==='/api/cloud/ticket'&&method==='POST'){
  await limit('cloud-ticket',session.id,120,60000);
  if(!/^[a-f0-9-]{36}$/.test(body.requestId||'')||!/^[a-f0-9]{64}$/.test(body.payloadHash||''))fail(400,'请求摘要无效。');
  return json({endpoint:'http://103.236.91.136:24336/api/cloud/direct',ticket:await sign(env,{iss:env.APP_ORIGIN,aud:'flowtodo-xiangyang',purpose:'cloud-call',sub:session.id,plan:session.plan,requestId:body.requestId,payloadHash:body.payloadHash,iat:Math.floor(now/1000),exp:Math.floor(now/1000)+120})});
 }
 if(path==='/api/cloud/receipt'&&method==='POST'){
  try{
   const [h,p,s]=body.receipt.split('.');if(JSON.parse(new TextDecoder().decode(decode(h))).alg!=='RS256')throw Error();
   const key=await crypto.subtle.importKey('spki',decode(env.AI_RECEIPT_PUBLIC),{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['verify']);
   if(!await crypto.subtle.verify('RSASSA-PKCS1-v1_5',key,decode(s),new TextEncoder().encode(h+'.'+p)))throw Error();
   const c=JSON.parse(new TextDecoder().decode(decode(p)));
   if(c.purpose!=='cloud-usage'||c.sub!==session.id||c.iss!=='flowtodo-xiangyang'||c.aud!==env.APP_ORIGIN||c.exp<now/1000||c.iat>now/1000+60||c.exp>c.iat+600)throw Error();
   for(const k of ['tasks','flows','aiPlans','bytes','revision'])if(!Number.isSafeInteger(c[k])||c[k]<0)throw Error();
   await q('INSERT INTO cloud_usage VALUES(?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET tasks=excluded.tasks,flows=excluded.flows,ai_plans=excluded.ai_plans,bytes=excluded.bytes,revision=excluded.revision,updated_at=excluded.updated_at WHERE excluded.revision>=cloud_usage.revision',session.id,c.tasks,c.flows,c.aiPlans,c.bytes,c.revision,now).run();
   return json({ok:true});
  }catch{fail(400,'存储用量回执无效。');}
 }
 if(path.startsWith('/api/cloud/')||path==='/api/account/avatar')fail(409,'云端内容保存在襄阳，请在最新版软件中查看、同步或删除。');
 return null;
}
