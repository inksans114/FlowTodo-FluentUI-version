import {issueIdentityTicket} from './identity-ticket.js';
// Only short-lived verification data is stored here. No subscription or record database.
export async function identityBroker({path,method,body,q,now,ownerHash,env,json,fail,limit,verify,deliver,ip,hostname,emailValid,codeHash}) {
 if (!path.startsWith('/api/identity/')) return null;
 if (!env.IDENTITY_BROKER_ENABLED || !env.IDENTITY_SIGNING_PKCS8 || !env.IDENTITY_ORIGIN) fail(503,'襄阳登录入口尚未启用。');
 if (method!=='POST') fail(405,'不支持该操作。');
 const email=String(body.email||'').trim().toLowerCase();
 if (!emailValid(email)) fail(400,'请输入有效邮箱。');
 if (path==='/api/identity/send-code') {
  if (!await verify(env,body,ip,hostname)) fail(400,'请重新完成人机验证。');
  await limit('mail-cooldown',email,1,60000);await limit('mail-address',email,10,86400000);await limit('mail-ip',ip,30,86400000);await limit('mail-global','all',200,86400000);
  const random=new Uint32Array(1);crypto.getRandomValues(random);
  const code=String(random[0]%1000000).padStart(6,'0'),hash=await codeHash(email,'identity',code);
  await q('INSERT INTO codes VALUES(?,?,?,?,?,0) ON CONFLICT(owner,email,purpose) DO UPDATE SET hash=excluded.hash,expires=excluded.expires,attempts=0',ownerHash,email,'identity',hash,now+600000).run();
  try {await deliver(env,email,code);}catch {await q('DELETE FROM codes WHERE owner=? AND email=? AND purpose=? AND hash=?',ownerHash,email,'identity',hash).run();fail(503,'邮件暂时无法投递。');}
  return json({message:'验证码已发送，10 分钟内有效。'});
 }
 if (path==='/api/identity/verify') {
  if (!/^[a-f0-9]{64}$/.test(body.state||'')) fail(400,'请从襄阳工作台重新开始登录。');
  if (!/^\d{6}$/.test(String(body.code||''))) fail(400,'请输入六位验证码。');
  await limit('verify',ip,30,900000);
  const hash=await codeHash(email,'identity',body.code);
  const consumed=await q('DELETE FROM codes WHERE owner=? AND email=? AND purpose=? AND hash=? AND expires>? AND attempts<5 RETURNING email',ownerHash,email,'identity',hash,now).first();
  if (!consumed) {await q('UPDATE codes SET attempts=attempts+1 WHERE owner=? AND email=? AND purpose=?',ownerHash,email,'identity').run();fail(400,'验证码错误、已使用或已过期。');}
  return json(await issueIdentityTicket(env,{email,name:String(body.name||'').trim().slice(0,40),state:body.state},now));
 }
 fail(404,'未找到登录验证接口。');
}
