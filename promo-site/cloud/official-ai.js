import {storageCall} from './storage-transport.js';
export async function officialAiApi({path,method,body,session,q,now,json,env,fail,limit}){
 if(!['/api/ai/chat','/api/admin/ai/grant'].includes(path))return null;
 if(method!=='POST')fail(405,'不支持该操作。');
 if(env.AI_DIRECT_ENABLED)fail(409,'官方通道已改为软件凭证直连。请重启最新版软件，在 AI 设置选择官方通道；会员确认后自动分配套餐额度。');
 env={...env,STORAGE_ORIGIN:env.AI_STORAGE_ORIGIN||env.STORAGE_ORIGIN,STORAGE_MODE:env.AI_STORAGE_ORIGIN?'direct':env.STORAGE_MODE};
 if(!env.STORAGE_KEY||!env.STORAGE_ORIGIN||!env.OFFICIAL_AI_ENABLED)fail(503,'官方通道正在准备中。');
 if(path==='/api/admin/ai/grant'){
  if(session.role!=='admin')fail(403,'需要管理员权限。');
  const user=body.userId?await q('SELECT * FROM users WHERE id=?',String(body.userId)).first():await q('SELECT * FROM users WHERE email=?',String(body.email||'').trim().toLowerCase()).first();if(!user)fail(404,'账户不存在。');
  if(!['free','lite','standard'].includes(body.plan)||!Number.isInteger(body.days)||body.days<1||body.days>366||!Number.isFinite(body.budgetUsd)||body.budgetUsd<=0||body.budgetUsd>5||!/^[a-f0-9-]{36}$/.test(String(body.grantId||'')))fail(400,'请选择方案、1–366 天及不超过 5 美元的中转金额上限。');
  const existing=await q('SELECT subscription_id FROM ai_entitlements WHERE user_id=?',user.id).first();if(existing?.subscription_id===body.grantId)return json({provisioned:true});
  let result;
  try{result=await storageCall(env,{...user,role:'admin'},'/api/ai/provision','POST',{grantId:body.grantId,budgetUsd:body.budgetUsd,days:body.days});}
  catch(error){return json({error:'襄阳 AI 后端暂时无法连接。',diagnostic:String(error.networkDetail||error.message||'').slice(0,180)},503);}
  if(result.status!==200)fail(result.status,result.data.error||'官方额度尚未开通。');
  const calls={free:5,lite:100,standard:300}[body.plan];
  await q('INSERT INTO ai_entitlements VALUES(?,?,0,0,?,?) ON CONFLICT(user_id) DO UPDATE SET call_limit=excluded.call_limit,used=0,reserved=0,expires=excluded.expires,subscription_id=excluded.subscription_id',user.id,calls,result.data.expires,body.grantId).run();
  await q('UPDATE users SET plan=? WHERE id=?',body.plan,user.id).run();return json({provisioned:true,limit:calls,expires:result.data.expires});
 }
 await limit('official-ai',session.id,5,60000);
 const id=String(body.requestId||'');if(!/^[a-f0-9-]{36}$/.test(id)||!Array.isArray(body.messages)||body.messages.length>40||!Number.isInteger(body.maxTokens)||body.maxTokens<1||body.maxTokens>8192)fail(400,'对话格式或长度无效。');
 const existing=await q('SELECT user_id,status,response FROM ai_requests WHERE id=?',id).first();if(existing){if(existing.user_id!==session.id)fail(409,'请求标识已被使用。');if(existing.status==='complete')return json(JSON.parse(existing.response));fail(409,'这次请求已处理或正在处理中，请勿重复发起。');}
 const entitlement=await q('UPDATE ai_entitlements SET reserved=reserved+1 WHERE user_id=? AND expires>? AND used+reserved<call_limit RETURNING subscription_id',session.id,now).first();if(!entitlement)fail(403,'官方 AI 额度尚未开通、已用完或已到期。');
 try{await q("INSERT INTO ai_requests VALUES(?,?,'pending',?,NULL,?)",id,session.id,now,entitlement.subscription_id).run();}catch{await q('UPDATE ai_entitlements SET reserved=MAX(0,reserved-1) WHERE user_id=? AND subscription_id=?',session.id,entitlement.subscription_id).run();fail(409,'请求标识已被使用。');}
 let result;
 try{result=await storageCall(env,session,'/api/ai/chat','POST',{requestId:id,messages:body.messages,maxTokens:body.maxTokens,temperature:body.temperature});}
 catch{await q("UPDATE ai_requests SET status='uncertain' WHERE id=?",id).run();fail(503,'请求结果暂时无法确认，请勿重复提交；额度已暂时保留，请稍后联系管理员核对。');}
 if(result.status!==200){await q("UPDATE ai_requests SET status='failed' WHERE id=?",id).run();await q('UPDATE ai_entitlements SET reserved=MAX(0,reserved-1) WHERE user_id=? AND subscription_id=?',session.id,entitlement.subscription_id).run();fail(result.status,result.data.error||'官方 AI 请求失败。');}
 await q("UPDATE ai_requests SET status='complete',response=? WHERE id=?",JSON.stringify(result.data),id).run();
 await q('UPDATE ai_entitlements SET reserved=MAX(0,reserved-1),used=used+1 WHERE user_id=? AND subscription_id=?',session.id,entitlement.subscription_id).run();return json(result.data);
}
