import { PLANS } from '../src/plans.js';
import { manualMembership, expireManualMembership } from './manual-membership.js';
import { deviceApi } from './device.js';
import { avatarApi } from './avatar.js';
import { storageCall } from './storage-transport.js';
import { officialAiApi } from './official-ai.js';
import { bridgeApi } from './bridge.js';
import { identityBroker } from './identity-broker.js';
import { nativeDevice } from './native-device.js';
import { directCloudApi } from './cloud-direct.js';
import { directAiApi,ensureDirectGrant } from './ai-direct.js';
const token = () => Array.from(crypto.getRandomValues(new Uint8Array(32)), x => x.toString(16).padStart(2, '0')).join('');
const hex = bytes => Array.from(new Uint8Array(bytes), x => x.toString(16).padStart(2, '0')).join('');
const sha = async text => hex(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)));
const fail = (status, message) => { throw Object.assign(new Error(message), { status }); };
const emailValid = email => /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?\.[a-zA-Z]{2,}$/.test(email) && email.length <= 254;
const publicUser = u => ({ id: u.id, email: u.email, name: u.name, plan: u.plan, role: u.role, balance: u.balance_cents / 100, createdAt: u.created_at, emailVerified: true });
const security = { 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'same-origin', 'X-Frame-Options': 'DENY', 'Permissions-Policy': 'camera=(), microphone=(), geolocation=()', 'Content-Security-Policy': "default-src 'self'; script-src 'self' https://challenges.cloudflare.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; object-src 'none'; base-uri 'self'; frame-ancestors 'none'", 'Strict-Transport-Security': 'max-age=31536000' };
const cookie = (name, value, seconds) => `${name}=${value}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=${seconds}`;
const items = rows => rows.map(r => ({ id: r.id, kind: r.kind, title: r.title, payload: JSON.parse(r.payload), version: r.version, updatedAt: r.updated_at, deletedAt: r.deleted_at }));
export function createWorker(deps = {}) {
  const deliver = deps.sendCode;
  const verify = deps.verify || (async (env, body, ip, hostname) => {
    const res = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', { method: 'POST', body: new URLSearchParams({ secret: env.TURNSTILE_SECRET, response: String(body.turnstileToken || ''), remoteip: ip }), signal: AbortSignal.timeout(8000) });
    const data = await res.json(); return data.success === true && data.hostname === hostname;
  });
  return {
    async fetch(request, env) {
      env={...env,STORAGE_FETCH:deps.storageFetch||fetch};
      const url = new URL(request.url), cookiesOut = [];
      const json = (data, status = 200, extra = {}) => {
        const headers = new Headers({ ...security, 'Cache-Control': 'no-store', 'Content-Type': 'application/json; charset=utf-8', ...extra });
        cookiesOut.forEach(c => headers.append('Set-Cookie', c)); return new Response(JSON.stringify(data), { status, headers });
      };
      if (!url.pathname.startsWith('/api/')) {
        const asset = await env.ASSETS.fetch(request), response = new Response(asset.body, asset);
        for (const [key, value] of Object.entries(security)) response.headers.set(key, value); return response;
      }
      const ready = !!(env.DB && env.TURNSTILE_SECRET && env.TURNSTILE_SITE_KEY && env.AUTH_SECRET && env.SMTP_USER && env.SMTP_PASSWORD);
      if(url.pathname.startsWith('/api/storage/bridge/')){
        if(env.STORAGE_MODE!=='reverse')return json({error:'国内连接暂未启用。'},503);
        if(url.origin!==env.APP_ORIGIN)return json({error:'请使用正式服务地址。'},403);
        return bridgeApi(request,env,json);
      }
      if (url.pathname === '/api/config') return json({ local: false, publicPreview: !ready, authMode: 'email-code', mailMode: ready ? 'smtp' : 'disabled', turnstileSiteKey: env.TURNSTILE_SITE_KEY || null, cloudEnabled: ready, cloudStorageMode: 'records', cloudDirectEnabled:!!env.CLOUD_DIRECT_ENABLED,storageLocation:env.CLOUD_DIRECT_ENABLED?'xiangyang-direct':env.STORAGE_ORIGIN?'xiangyang':'cloudflare-d1', desktopLoginEnabled:true,paymentsEnabled: false, manualPaymentsEnabled:!!env.MANUAL_PAYMENTS_ENABLED, aiEnabled: !!env.OFFICIAL_AI_READY,aiDirectEnabled:!!env.AI_DIRECT_ENABLED, plans: PLANS });
      if (url.pathname === '/api/status') return json({ ok: true, ready, cloudEnabled: ready, paymentsEnabled: false });
      try {
        if (!ready) fail(503, '账户服务配置尚未完成，请稍后再试。');
        if (url.origin !== env.APP_ORIGIN) fail(403, '请通过正式网站访问账户服务。');
        const now = Date.now(), q = (sql, ...args) => env.DB.prepare(sql).bind(...args);
        const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
        async function limit(bucket, identity, max, window) {
          const key = `${bucket}:${await sha(identity)}:${Math.floor(now / window)}`;
          const row = await q('INSERT INTO rate_limits(key,count,expires) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1 RETURNING count', key, now + window * 2).first();
          if (row.count > max) fail(429, '请求过于频繁，请稍后再试。');
        }
        await limit('api', ip, 180, 60000);
        const write = !['GET', 'HEAD'].includes(request.method); let body = {};
        if (write) {
          if (request.headers.get('Origin') !== env.APP_ORIGIN || request.headers.get('X-FlowTodo-Request') !== '1' || !request.headers.get('Content-Type')?.startsWith('application/json')) fail(403, '请求来源校验失败。');
          const bodyLimit = url.pathname === '/api/account/avatar' ? 180000 : url.pathname === '/api/ai/chat' ? 100000 : 32768;
          if (Number(request.headers.get('Content-Length') || 0) > bodyLimit) fail(413, '请求过大。');
          const raw = await request.text(); if (new TextEncoder().encode(raw).length > bodyLimit) fail(413, '请求过大。');
          try { body = JSON.parse(raw); } catch { fail(400, '请求格式不正确。'); }
          if (!body || typeof body !== 'object' || Array.isArray(body)) fail(400, '请求格式不正确。');
        }
        const cookies = Object.fromEntries((request.headers.get('Cookie') || '').split(';').map(c => c.trim().split('=')));
        let owner = cookies.flowtodo_guest;
        if (!/^[a-f0-9]{64}$/.test(owner || '')) { owner = token(); cookiesOut.push(cookie('flowtodo_guest', owner, 3600)); }
        const ownerHash = await sha(owner);
        const bearer = /^Bearer ([a-f0-9]{64})$/.exec(request.headers.get('Authorization') || '');
        const session = bearer ? await q('SELECT u.*,s.hash AS session_hash,s.id AS device_id FROM device_sessions s JOIN users u ON u.id=s.user_id WHERE s.hash=? AND s.expires>?', await sha(bearer[1]), now).first() : /^[a-f0-9]{64}$/.test(cookies.flowtodo_session || '') ? await q('SELECT u.*,s.csrf,s.hash AS session_hash FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.hash=? AND s.expires>?', await sha(cookies.flowtodo_session), now).first() : null;
        const auth = () => { if (!session) fail(401, '请先登录你的账户。'); if (write && !bearer && request.headers.get('X-CSRF-Token') !== session.csrf) fail(403, '安全令牌已失效，请刷新页面。'); return session; };
        if(url.pathname==='/api/device/authorize')auth();
        const deviceResult=await deviceApi({path:url.pathname,method:request.method,body,q,now,token,sha,session,bearer,json,limit,env,fail});if(deviceResult)return deviceResult;
        async function codeHash(email, purpose, code) {
          const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(env.AUTH_SECRET), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
          return hex(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(`${ownerHash}:${email}:${purpose}:${code}`)));
        }
        const email = String(body.email || '').trim().toLowerCase();
        const nativeResult=await nativeDevice({path:url.pathname,method:request.method,body,q,now,env,json,fail,limit,deliver,ip,sha,token,emailValid});if(nativeResult)return nativeResult;
        const identityResult=await identityBroker({path:url.pathname,method:request.method,body,q,now,ownerHash,env,json,fail,limit,verify,deliver,ip,hostname:url.hostname,emailValid,codeHash});if(identityResult)return identityResult;
        if (url.pathname === '/api/auth/send-code' && request.method === 'POST') {
          if (!emailValid(email) || !['login', 'register'].includes(body.purpose)) fail(400, '请输入有效邮箱并选择登录或注册。');
          if (!await verify(env, body, ip, url.hostname)) fail(400, '请重新完成人机验证。');
          await limit('mail-cooldown', email, 1, 60000); await limit('mail-address', email, 10, 86400000); await limit('mail-ip', ip, 30, 86400000); await limit('mail-global', 'all', 200, 86400000);
          const random = new Uint32Array(1); crypto.getRandomValues(random);
          const code = String(random[0] % 1000000).padStart(6, '0'), hash = await codeHash(email, body.purpose, code);
          await q('INSERT INTO codes VALUES(?,?,?,?,?,0) ON CONFLICT(owner,email,purpose) DO UPDATE SET hash=excluded.hash,expires=excluded.expires,attempts=0', ownerHash, email, body.purpose, hash, now + 600000).run();
          try { await deliver(env, email, code); } catch { await q('DELETE FROM codes WHERE owner=? AND email=? AND purpose=? AND hash=?', ownerHash, email, body.purpose, hash).run(); fail(503, '邮件暂时无法投递，请稍后再试。'); }
          return json({ message: '验证码已发送，10 分钟内有效。' });
        }
        if (['/api/auth/login', '/api/auth/register'].includes(url.pathname) && request.method === 'POST') {
          const purpose = url.pathname.endsWith('register') ? 'register' : 'login', name = String(body.name || '').trim();
          if (!emailValid(email) || !/^\d{6}$/.test(String(body.code || ''))) fail(400, '请输入邮箱和六位验证码。');
          if (purpose === 'register' && (!name || name.length > 40 || body.acceptTerms !== true)) fail(400, '请填写昵称并阅读同意服务条款。');
          await limit('verify', ip, 30, 900000);
          const hash = await codeHash(email, purpose, body.code);
          const consumed = await q('DELETE FROM codes WHERE owner=? AND email=? AND purpose=? AND hash=? AND expires>? AND attempts<5 RETURNING email', ownerHash, email, purpose, hash, now).first();
          if (!consumed) { await q('UPDATE codes SET attempts=attempts+1 WHERE owner=? AND email=? AND purpose=?', ownerHash, email, purpose).run(); fail(400, '验证码错误、已使用或已过期，请重新获取。'); }
          let user = await q('SELECT * FROM users WHERE email=?', email).first();
          if (purpose === 'register') {
            if (user) fail(409, '该邮箱已注册，请登录。');
            const role = email === String(env.ADMIN_EMAIL || '').toLowerCase() ? 'admin' : 'user';
            await q('INSERT INTO users(id,email,name,role,created_at) VALUES(?,?,?,?,?) ON CONFLICT(email) DO NOTHING', crypto.randomUUID(), email, name, role, new Date(now).toISOString()).run();
            user = await q('SELECT * FROM users WHERE email=?', email).first();
          }
          if (!user) fail(400, '该邮箱尚未注册，请先创建账户。');
          const rawSession = token(), csrf = token(); if (session) await q('DELETE FROM sessions WHERE hash=?', session.session_hash).run();
          await q('INSERT INTO sessions VALUES(?,?,?,?)', await sha(rawSession), user.id, csrf, now + 7 * 86400000).run();
          cookiesOut.push(cookie('flowtodo_session', rawSession, 7 * 86400)); return json({ user: publicUser(user), csrf });
        }
        auth();
        await expireManualMembership(q,session,now);
        const directAi=await directAiApi({path:url.pathname,method:request.method,body,session,q,now,json,env,fail,limit});if(directAi)return directAi;
        const manualResult=await manualMembership({path:url.pathname,method:request.method,body,session,q,now,json,env,fail});if(manualResult)return manualResult;
        const directCloud=await directCloudApi({path:url.pathname,method:request.method,body,session,q,now,json,env,fail,limit});if(directCloud)return directCloud;
        const remoteStore=!!(env.STORAGE_ORIGIN&&env.STORAGE_KEY);
        const aiResult=await officialAiApi({path:url.pathname,method:request.method,body,session,q,now,json,env,fail,limit});if(aiResult)return aiResult;
        if(remoteStore&&(url.pathname.startsWith('/api/cloud/')||url.pathname==='/api/account/avatar')){const result=await storageCall(env,session,url.pathname+url.search,request.method,body);return json(result.data,result.status);}
        const avatarResult=await avatarApi({path:url.pathname,method:request.method,body,q,session,json,fail,now});if(avatarResult)return avatarResult;
        if (url.pathname === '/api/auth/logout' && request.method === 'POST') { await q(`DELETE FROM ${bearer?'device_sessions':'sessions'} WHERE hash=?`, session.session_hash).run(); cookiesOut.push(cookie('flowtodo_session', '', 0)); return json({ ok: true }); }
        if (url.pathname === '/api/account/sessions' && request.method === 'DELETE') { await q('DELETE FROM sessions WHERE user_id=?', session.id).run(); await q('DELETE FROM device_sessions WHERE user_id=?',session.id).run();cookiesOut.push(cookie('flowtodo_session', '', 0)); return json({ ok: true }); }
        if(url.pathname==='/api/account/devices'&&request.method==='GET'){const rows=await q('SELECT id,name,created_at,expires FROM device_sessions WHERE user_id=? AND expires>?',session.id,now).all();return json({devices:rows.results});}
        if(url.pathname==='/api/account/device'&&request.method==='DELETE'){await q('DELETE FROM device_sessions WHERE user_id=? AND id=?',session.id,String(body.id||'')).run();return json({ok:true});}
        if (url.pathname === '/api/account/profile' && request.method === 'PATCH') {
          const name = String(body.name || '').trim(); if (!name || name.length > 40) fail(400, '昵称需要 1–40 个字符。');
          await q('UPDATE users SET name=? WHERE id=?', name, session.id).run(); return json({ user: publicUser({ ...session, name }) });
        }
        if (url.pathname === '/api/account' && request.method === 'GET') {
          if(env.AI_DIRECT_ENABLED)await ensureDirectGrant(q,session,now);
          if(env.CLOUD_DIRECT_ENABLED){
            const u=await q('SELECT * FROM cloud_usage WHERE user_id=?',session.id).first();
            const ai=await q('SELECT call_limit,used,reserved,expires FROM ai_entitlements WHERE user_id=?',session.id).first();
            return json({user:{...publicUser(session),avatarUrl:''},avatar:{data:null,revision:0,unavailable:true},csrf:session.csrf,usage:{tasks:u?.tasks||0,flows:u?.flows||0,aiPlans:u?.ai_plans||0,storageMB:Math.ceil((u?.bytes||0)/1048576*100)/100,aiCalls:ai?.used||0},cloud:{connected:!!u,location:'xiangyang-direct',items:[],updatedAt:u?.updated_at||0},officialAI:{connected:!!env.OFFICIAL_AI_READY,active:!!(ai&&ai.expires>now),limit:ai?.call_limit||0,used:ai?.used||0,remaining:ai&&ai.expires>now?Math.max(0,ai.call_limit-ai.used-ai.reserved):0,expires:ai?.expires||0},transactions:[],interests:[]});
          }
          if(remoteStore){let result;try{result=await storageCall(env,session,'/api/cloud/summary');}catch{result={status:503};}if(result.status!==200)result={data:{usage:{tasks:null,flows:null,aiPlans:null,aiCalls:0,storageMB:null},cloud:{connected:false,items:[],error:'襄阳存储暂时无法连接，请稍后重试。'},avatar:{data:null,revision:0,unavailable:true}}};const interests=await q('SELECT plan,cycle,created_at FROM interests WHERE user_id=?',session.id).all();const ai=await q('SELECT call_limit,used,reserved,expires FROM ai_entitlements WHERE user_id=?',session.id).first();result.data.usage.aiCalls=ai?.used||0;return json({user:{...publicUser(session),avatarUrl:result.data.avatar.data},csrf:session.csrf,...result.data,officialAI:{connected:!!env.OFFICIAL_AI_ENABLED,active:!!(env.OFFICIAL_AI_READY&&ai&&ai.expires>now),limit:ai?.call_limit||0,used:ai?.used||0,remaining:ai&&ai.expires>now?Math.max(0,ai.call_limit-ai.used-ai.reserved):0,expires:ai?.expires||0},transactions:[],interests:interests.results});}
          const counts = await q('SELECT kind,COUNT(*) AS count,SUM(bytes) AS bytes FROM cloud_items WHERE user_id=? AND deleted_at IS NULL GROUP BY kind', session.id).all();
          const usage = { tasks: 0, flows: 0, aiPlans: 0, aiCalls: 0, storageMB: 0 };
          for (const row of counts.results) { usage[row.kind] = row.count; usage.storageMB += row.bytes / 1048576; }
          usage.storageMB = Math.ceil(usage.storageMB * 100) / 100;
          const rows = await q('SELECT * FROM cloud_items WHERE user_id=? AND deleted_at IS NULL ORDER BY updated_at DESC LIMIT 5', session.id).all();
          const interests = await q('SELECT plan,cycle,created_at FROM interests WHERE user_id=?', session.id).all();
          const avatar=await q('SELECT data,revision FROM avatars WHERE user_id=?',session.id).first();
          const ai=await q('SELECT call_limit,used,reserved,expires FROM ai_entitlements WHERE user_id=?',session.id).first();
          usage.aiCalls=ai?.used||0;
          return json({ user: {...publicUser(session),avatarUrl:avatar?.data||''},avatar:{data:avatar?.data||'',revision:avatar?.revision||0},csrf: session.csrf, usage, cloud: { connected: true, location:'cloudflare-d1',items: items(rows.results) },officialAI:{connected:!!env.OFFICIAL_AI_ENABLED,active:!!(env.OFFICIAL_AI_READY&&ai&&ai.expires>now),limit:ai?.call_limit||0,used:ai?.used||0,remaining:env.OFFICIAL_AI_READY&&ai&&ai.expires>now?Math.max(0,ai.call_limit-ai.used-ai.reserved):0,expires:ai?.expires||0}, transactions: [], interests: interests.results });
        }
        if (url.pathname === '/api/membership/interest' && request.method === 'POST') {
          if (!['lite', 'standard'].includes(body.plan) || !['monthly', 'annual'].includes(body.cycle)) fail(400, '请选择有效方案。');
          await q('INSERT INTO interests VALUES(?,?,?,?) ON CONFLICT(user_id,plan,cycle) DO UPDATE SET created_at=excluded.created_at', session.id, body.plan, body.cycle, new Date(now).toISOString()).run(); return json({ message: '升级意向已保存，未扣款。' });
        }
        if (url.pathname === '/api/cloud/export' && request.method === 'GET') {
          const rows = await q('SELECT * FROM cloud_items WHERE user_id=? ORDER BY updated_at DESC', session.id).all(); return json({ format: 'flowtodo-cloud-v1', exportedAt: new Date(now).toISOString(), items: items(rows.results) }, 200, { 'Content-Disposition': 'attachment; filename="flowtodo-cloud.json"' });
        }
        if (url.pathname === '/api/cloud/items' && request.method === 'GET') {
          const kind = url.searchParams.get('kind'), trash = url.searchParams.get('trash') === '1', after = url.searchParams.get('after') || '';
          if (kind && !['tasks', 'flows', 'aiPlans'].includes(kind)) fail(400, '未知数据类型。');
          const rows = await q(`SELECT * FROM cloud_items WHERE user_id=? AND deleted_at IS ${trash ? 'NOT ' : ''}NULL AND (?='' OR kind=?) AND id>? ORDER BY id LIMIT 101`, session.id, kind || '', kind || '', after).all(); return json({ items: items(rows.results.slice(0, 100)), next: rows.results.length > 100 ? rows.results[99].id : null });
        }
        if (url.pathname === '/api/cloud/items' && request.method === 'POST') {
          const title = String(body.title || '').trim(), payload = JSON.stringify(body.payload ?? {}), bytes = new TextEncoder().encode(payload + title).length;
          if (!['tasks', 'flows', 'aiPlans'].includes(body.kind) || !title || title.length > 120 || bytes > 16384 || typeof body.payload !== 'object' || !body.payload || Array.isArray(body.payload)) fail(400, '请选择类型，填写标题；JSON 对象最多 16 KB。');
          const syncUid=body.payload._syncUid;
          if(syncUid!==undefined&&(!/^(?:[a-f0-9]{32}|[a-f0-9-]{36})$/.test(syncUid)))fail(400,'同步标识无效。');
          if(syncUid){const prior=await q("SELECT * FROM cloud_items WHERE user_id=? AND json_extract(payload,'$._syncUid')=?",session.id,syncUid).first();if(prior)return json({item:items([prior])[0]},201);}
          const id = crypto.randomUUID(), date = new Date(now).toISOString();
          try{await q('INSERT INTO cloud_items(id,user_id,kind,title,payload,bytes,updated_at) VALUES(?,?,?,?,?,?,?)', id, session.id, body.kind, title, payload, bytes, date).run();}catch(error){if(syncUid){const prior=await q("SELECT * FROM cloud_items WHERE user_id=? AND json_extract(payload,'$._syncUid')=?",session.id,syncUid).first();if(prior)return json({item:items([prior])[0]},201);}throw error;}return json({ item: { id, kind: body.kind, title, payload: body.payload, version: 1, updatedAt: date, deletedAt: null } }, 201);
        }
        const match = url.pathname.match(/^\/api\/cloud\/items\/([a-f0-9-]{36})(\/restore)?$/);
        if (match && ['PATCH', 'DELETE', 'POST'].includes(request.method)) {
          const prior = await q('SELECT * FROM cloud_items WHERE id=? AND user_id=?', match[1], session.id).first(); if (!prior) fail(404, '记录不存在。');
          if (body.version !== prior.version) fail(409, '记录已在另一处修改，请刷新后重试。');
          let title = prior.title, payload = prior.payload, deleted = prior.deleted_at;
          if (request.method === 'DELETE' && !match[2]) deleted = new Date(now).toISOString();
          else if (request.method === 'POST' && match[2] && deleted) deleted = null;
          else if (request.method === 'PATCH' && !match[2] && !deleted) { title = String(body.title || '').trim(); payload = JSON.stringify(body.payload); if (!title || title.length > 120 || !body.payload || typeof body.payload !== 'object' || Array.isArray(body.payload)) fail(400, '标题或 JSON 对象不正确。'); }
          else fail(400, '该操作不适用于当前记录。');
          const bytes = new TextEncoder().encode(payload + title).length; if (bytes > 16384) fail(413, '单条记录最多 16 KB。');
          const changed = await q('UPDATE cloud_items SET title=?,payload=?,bytes=?,deleted_at=?,version=version+1,updated_at=? WHERE id=? AND user_id=? AND version=?', title, payload, bytes, deleted, new Date(now).toISOString(), prior.id, session.id, prior.version).run(); if (!changed.meta.changes) fail(409, '记录已更新，请刷新后重试。'); return json({ ok: true });
        }
        if (url.pathname === '/api/admin/overview' && request.method === 'GET') {
          if (session.role !== 'admin') fail(403, '需要管理员权限。');
          const stats = await q('SELECT (SELECT COUNT(*) FROM users) AS users,(SELECT COUNT(*) FROM cloud_items WHERE deleted_at IS NULL) AS records,(SELECT COALESCE(SUM(bytes),0) FROM cloud_items) AS bytes').first();if(env.CLOUD_DIRECT_ENABLED){const totals=await q('SELECT COALESCE(SUM(tasks+flows+ai_plans),0) records,COALESCE(SUM(bytes),0) bytes FROM cloud_usage').first();Object.assign(stats,totals);}if(remoteStore){const remote=await storageCall(env,session,'/api/cloud/admin-summary');if(remote.status!==200)fail(503,'后台统计暂时不可用。');Object.assign(stats,remote.data);} const users = await q('SELECT id,email,name,plan,role,created_at FROM users ORDER BY created_at DESC LIMIT 100').all(); return json({ stats, users: users.results });
        }
        if (url.pathname === '/api/payments/topup') fail(503, '支付渠道尚未接入。'); fail(404, '未找到此功能。');
      } catch (error) {
        if(/^storage_[a-z_0-9]+$/.test(error.message||'')) console.warn('FLOWTODO_BACKEND',error.message);
        const message = String(error.message || '');
        if (message.includes('record_quota') || message.includes('storage_quota')) return json({ error: '已达到当前会员的云端额度，请先导出或整理记录。' }, 409);
        return json({ error: error.status ? error.message : '服务暂时不可用，请稍后重试。',code:/^storage_[a-z_0-9]+$/.test(error.message||'')?error.message:undefined }, error.status || 503);
      }
    },
    async scheduled(_event, env) {
      const now = Date.now(); await env.DB.batch([env.DB.prepare('DELETE FROM sessions WHERE expires<?').bind(now),env.DB.prepare('DELETE FROM device_sessions WHERE expires<?').bind(now),env.DB.prepare('DELETE FROM device_requests WHERE expires<?').bind(now), env.DB.prepare('DELETE FROM codes WHERE expires<?').bind(now), env.DB.prepare('DELETE FROM rate_limits WHERE expires<?').bind(now), env.DB.prepare('DELETE FROM cloud_items WHERE deleted_at<?').bind(new Date(now - 7 * 86400000).toISOString())]);
    },
  };
}
