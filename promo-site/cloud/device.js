export async function deviceApi({path,method,body,q,now,token,sha,session,bearer,json,limit,env,fail}) {
 if(path==='/api/device/start'&&method==='POST'){
  await limit('device-start', 'all', 1000,86400000);
  const raw=token(),code=token().slice(0,10).toUpperCase(),name=String(body.name||'FlowTodo 桌面端').slice(0,80);
  await q('INSERT INTO device_requests(hash,user_code,name,expires) VALUES(?,?,?,?)',await sha(raw),code,name,now+300000).run();
  return json({deviceCode:raw,userCode:code,verificationUri:env.APP_ORIGIN+'/connect?code='+code,expiresIn:300,interval:5});
 }
 if(path==='/api/device/poll'&&method==='POST'){
  if(!/^[a-f0-9]{64}$/.test(String(body.deviceCode||'')))fail(400,'登录请求无效。');
  const hash=await sha(body.deviceCode),pending=await q('SELECT * FROM device_requests WHERE hash=? AND expires>?',hash,now).first();
  if(!pending)fail(410,'登录请求已到期，请重新开始。');
  if(!pending.user_id)return json({pending:true},202);
  const claimed=await q('DELETE FROM device_requests WHERE hash=? AND user_id IS NOT NULL AND expires>? RETURNING user_id,name',hash,now).first();
  if(!claimed)fail(410,'该登录请求已被使用。');
  const raw=token(),id=crypto.randomUUID(),expires=now+30*86400000;
  await q('INSERT INTO device_sessions VALUES(?,?,?,?,?,?)',await sha(raw),id,claimed.user_id,claimed.name,new Date(now).toISOString(),expires).run();
  return json({accessToken:raw,expiresAt:expires,deviceId:id});
 }
 if(path==='/api/device/authorize'&&method==='POST'){
  if(!session||bearer)fail(401,'请在官网登录后确认连接。');
  if(!/^[A-F0-9]{10}$/.test(String(body.userCode||'')))fail(400,'设备确认码无效。');
  const pending=await q('SELECT name FROM device_requests WHERE user_code=? AND expires>? AND user_id IS NULL',body.userCode,now).first();
  if(!pending)fail(410,'登录请求已到期或已确认。');
  if(body.confirm!==true)return json({name:pending.name,userCode:body.userCode});
  await q('UPDATE device_requests SET user_id=? WHERE user_code=? AND expires>? AND user_id IS NULL',session.id,body.userCode,now).run();return json({approved:true});
 }
 return null;
}
