// Pilot desktop login: mailbox ownership remains mandatory; no fixed login code.
export async function nativeDevice({path,method,body,q,now,env,json,fail,limit,deliver,ip,sha,token,emailValid}) {
 if(!['/api/native/send-code','/api/native/verify'].includes(path))return null;
 if(!env.NATIVE_LOGIN_ENABLED)fail(503,'软件内邮箱登录暂未启用。');
 if(method!=='POST')fail(405,'不支持该操作。');
 const email=String(body.email||'').trim().toLowerCase(),device=String(body.deviceCode||'');
 if(!emailValid(email)||! /^[a-f0-9]{64}$/.test(device))fail(400,'请输入有效邮箱并重新开始登录。');
 const owner=await sha(device),purpose='native-login';
 const pending=await q('SELECT * FROM device_requests WHERE hash=? AND expires>? AND user_id IS NULL',owner,now).first();
 if(!pending)fail(410,'登录请求已到期，请重新获取验证码。');
 const user=await q('SELECT id FROM users WHERE email=?',email).first();
 async function digest(code){const key=await crypto.subtle.importKey('raw',new TextEncoder().encode(env.AUTH_SECRET),{name:'HMAC',hash:'SHA-256'},false,['sign']);const bytes=await crypto.subtle.sign('HMAC',key,new TextEncoder().encode(`${owner}:${email}:${purpose}:${code}`));return Array.from(new Uint8Array(bytes),x=>x.toString(16).padStart(2,'0')).join('');}
 if(path.endsWith('/send-code')){
  await limit('mail-cooldown',email,1,60000);await limit('mail-address',email,10,86400000);await limit('mail-ip',ip,30,86400000);await limit('mail-global','all',200,86400000);
  if(user){
   const random=new Uint32Array(1);crypto.getRandomValues(random);const code=String(random[0]%1000000).padStart(6,'0'),hash=await digest(code);
   await q('INSERT INTO codes VALUES(?,?,?,?,?,0) ON CONFLICT(owner,email,purpose) DO UPDATE SET hash=excluded.hash,expires=excluded.expires,attempts=0',owner,email,purpose,hash,now+600000).run();
   try{await deliver(env,email,code);}catch{await q('DELETE FROM codes WHERE owner=? AND email=? AND purpose=?',owner,email,purpose).run();fail(503,'验证码暂时无法发送，请稍后重试。');}
  }
  return json({message:'如果邮箱已经注册，验证码将发送至邮箱。'});
 }
 await limit('verify',ip,30,900000);
 const code=String(body.code||'');
 if(!/^[0-9]{6}$/.test(code))fail(400,'请输入六位验证码。');
 const consumed=await q('DELETE FROM codes WHERE owner=? AND email=? AND purpose=? AND hash=? AND expires>? AND attempts<5 RETURNING email',owner,email,purpose,await digest(code),now).first();
 if(!consumed||!user){await q('UPDATE codes SET attempts=attempts+1 WHERE owner=? AND email=? AND purpose=?',owner,email,purpose).run();fail(400,'验证码错误、已使用或已过期；新用户请先注册。');}
 const claimed=await q('DELETE FROM device_requests WHERE hash=? AND expires>? AND user_id IS NULL RETURNING name',owner,now).first();
 if(!claimed)fail(410,'登录请求已使用，请重新开始。');
 const raw=token(),id=crypto.randomUUID(),expires=now+30*86400000;
 await q('INSERT INTO device_sessions VALUES(?,?,?,?,?,?)',await sha(raw),id,user.id,claimed.name,new Date(now).toISOString(),expires).run();
 return json({accessToken:raw,deviceId:id,expiresAt:expires});
}
