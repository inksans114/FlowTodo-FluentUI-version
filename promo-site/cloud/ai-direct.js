const bytes=v=>new TextEncoder().encode(v);
const b64=b=>btoa(String.fromCharCode(...new Uint8Array(b))).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');
const decode=s=>Uint8Array.from(atob(s.replaceAll('-','+').replaceAll('_','/')),c=>c.charCodeAt(0));
export async function sign(env,claims){
 const key=await crypto.subtle.importKey('pkcs8',decode(env.AI_TICKET_PRIVATE),{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['sign']);
 const message=b64(bytes(JSON.stringify({alg:'RS256',typ:'JWT'})))+'.'+b64(bytes(JSON.stringify(claims)));
 return message+'.'+b64(await crypto.subtle.sign('RSASSA-PKCS1-v1_5',key,bytes(message)));
}
export async function ensureDirectGrant(q,session,now){
 let grant=await q('SELECT * FROM ai_entitlements WHERE user_id=?',session.id).first();
 const membership=await q('SELECT plan,expires FROM manual_memberships WHERE user_id=?',session.id).first();
 const calls={free:5,lite:100,standard:300}[session.plan];
 const expiry=session.plan==='free'?now+365*86400000:Math.min(membership?.plan===session.plan?membership.expires:now+30*86400000,now+30*86400000);
 if(!grant||(session.plan!=='free'&&membership?.expires>now&&(grant.call_limit!==calls||grant.expires<=now))){
  const id=crypto.randomUUID();
  if(!grant)await q('INSERT INTO ai_entitlements VALUES(?,?,0,0,?,?) ON CONFLICT(user_id) DO NOTHING',session.id,calls,expiry,id).run();
  else await q('UPDATE ai_entitlements SET call_limit=?,used=0,reserved=0,expires=?,subscription_id=? WHERE user_id=? AND subscription_id=?',calls,expiry,id,session.id,grant.subscription_id).run();
  grant=await q('SELECT * FROM ai_entitlements WHERE user_id=?',session.id).first();
 }
 if(session.plan!=='free'&&membership?.plan===session.plan&&membership.expires<grant.expires){
  await q('UPDATE ai_entitlements SET expires=? WHERE user_id=? AND subscription_id=?',membership.expires,session.id,grant.subscription_id).run();grant={...grant,expires:membership.expires};
 }
 return grant;
}
export async function directAiApi({path,method,body,session,q,now,json,env,fail,limit}){
 if(!['/api/ai/ticket','/api/ai/receipt'].includes(path))return null;
 if(method!=='POST')fail(405,'不支持该操作。');
 if(!env.AI_DIRECT_ENABLED||!env.AI_TICKET_PRIVATE||!env.AI_RECEIPT_PUBLIC)fail(503,'官方直连通道尚未启用。');
 if(path==='/api/ai/receipt'){
  const raw=String(body.receipt||'');if(raw.length>4096)fail(400,'回执无效。');
  try{
   const [h,p,s]=raw.split('.');const header=JSON.parse(new TextDecoder().decode(decode(h)));
   if(header.alg!=='RS256'||header.typ!=='JWT')throw Error();
   const key=await crypto.subtle.importKey('spki',decode(env.AI_RECEIPT_PUBLIC),{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['verify']);
   if(!await crypto.subtle.verify('RSASSA-PKCS1-v1_5',key,decode(s),bytes(h+'.'+p)))throw Error();
   const c=JSON.parse(new TextDecoder().decode(decode(p)));
   if(c.purpose!=='ai-receipt'||c.sub!==session.id||c.iss!=='flowtodo-xiangyang'||c.aud!==env.APP_ORIGIN||c.exp<now/1000||c.iat>now/1000+5||c.exp>c.iat+600||!Number.isInteger(c.used)||c.used<0)throw Error();
   await q('UPDATE ai_entitlements SET used=MAX(used,?),reserved=0 WHERE user_id=? AND subscription_id=?',c.used,session.id,c.grant).run();
   return json({ok:true});
  }catch{fail(400,'襄阳调用回执无效或已过期。');}
 }
 await limit('official-ai-ticket',session.id,5,60000);
 if(!/^[a-f0-9-]{36}$/.test(String(body.requestId||''))||!/^[a-f0-9]{64}$/.test(String(body.payloadHash||'')))fail(400,'请求标识或摘要无效。');
 const grant=await ensureDirectGrant(q,session,now);
 if(grant.expires<=now||grant.used>=grant.call_limit)fail(403,'官方 AI 额度已用完或已到期。');
 const c={iss:env.APP_ORIGIN,aud:'flowtodo-xiangyang',purpose:'ai-call',sub:session.id,grant:grant.subscription_id,plan:session.plan,limit:grant.call_limit,budgetUsd:{free:0.02,lite:0.2,standard:0.4}[session.plan],grantExpires:grant.expires,requestId:body.requestId,payloadHash:body.payloadHash,iat:Math.floor(now/1000),exp:Math.floor(now/1000)+120};
 return json({ticket:await sign(env,c),endpoint:'http://103.236.91.136:24336/api/ai/direct',remaining:Math.max(0,grant.call_limit-grant.used)});
}
