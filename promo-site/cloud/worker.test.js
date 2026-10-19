import { test } from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { createWorker } from './worker-core.js';
import { bridgeExchange } from './bridge.js';

test('direct storage exposes counters only and rejects forged or stale usage receipts',async()=>{
 const f=fixture(),b=f.browser();await f.register(b,'storage-direct@example.com');f.env.CLOUD_DIRECT_ENABLED=true;
 const keys=await crypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
 f.env.AI_TICKET_PRIVATE=Buffer.from(await crypto.subtle.exportKey('pkcs8',keys.privateKey)).toString('base64');f.env.AI_RECEIPT_PUBLIC=Buffer.from(await crypto.subtle.exportKey('spki',keys.publicKey)).toString('base64');
 const account=(await b.req('/api/account')).data;assert.deepEqual(account.cloud.items,[]);assert.equal(account.avatar.data,null);
 assert.equal((await b.req('/api/cloud/items')).status,409);assert.equal((await b.req('/api/account/avatar',{data:'private'},'PUT')).status,409);
 assert.equal((await b.req('/api/cloud/receipt',{receipt:'fake'})).status,400);
 const sign=async revision=>{const now=Math.floor(Date.now()/1000),c={iss:'flowtodo-xiangyang',aud:f.env.APP_ORIGIN,purpose:'cloud-usage',sub:account.user.id,tasks:revision,flows:0,aiPlans:0,bytes:42,revision,iat:now,exp:now+600};const msg=Buffer.from(JSON.stringify({alg:'RS256',typ:'JWT'})).toString('base64url')+'.'+Buffer.from(JSON.stringify(c)).toString('base64url');return msg+'.'+Buffer.from(await crypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(msg))).toString('base64url');};
 assert.equal((await b.req('/api/cloud/receipt',{receipt:await sign(2)})).status,200);
 await b.req('/api/cloud/receipt',{receipt:await sign(1)});assert.equal((await b.req('/api/account')).data.usage.tasks,2);
 assert.equal(f.sqlite.prepare('SELECT COUNT(*) n FROM cloud_items').get().n,0);assert.equal(f.sqlite.prepare('SELECT COUNT(*) n FROM avatars').get().n,0);f.sqlite.close();
});

test('direct official tickets use server membership, preserve trial grants and accept only signed usage',async()=>{
 const f=fixture(),browser=f.browser();await f.register(browser,'direct@example.com');
 const keys=await crypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
 const encode=b=>Buffer.from(b).toString('base64url');
 f.env.AI_TICKET_PRIVATE=Buffer.from(await crypto.subtle.exportKey('pkcs8',keys.privateKey)).toString('base64');f.env.AI_RECEIPT_PUBLIC=Buffer.from(await crypto.subtle.exportKey('spki',keys.publicKey)).toString('base64');f.env.AI_DIRECT_ENABLED=true;f.env.OFFICIAL_AI_ENABLED=true;f.env.OFFICIAL_AI_READY=true;
 const account=(await browser.req('/api/account')).data;assert.equal(account.officialAI.remaining,5);assert.equal(account.officialAI.active,true);
 const ticket=(await browser.req('/api/ai/ticket',{requestId:crypto.randomUUID(),payloadHash:'a'.repeat(64),plan:'standard',limit:300})).data;
 const claims=JSON.parse(Buffer.from(ticket.ticket.split('.')[1],'base64url'));assert.equal(claims.limit,5);assert.equal(claims.plan,'free');assert.equal(claims.budgetUsd,.02);
 const first=f.sqlite.prepare('SELECT subscription_id FROM ai_entitlements').get().subscription_id;await browser.req('/api/account');assert.equal(f.sqlite.prepare('SELECT subscription_id FROM ai_entitlements').get().subscription_id,first);
 assert.equal((await browser.req('/api/ai/receipt',{receipt:'forged'})).status,400);
 const now=Math.floor(Date.now()/1000),receiptClaims={iss:'flowtodo-xiangyang',aud:f.env.APP_ORIGIN,purpose:'ai-receipt',sub:account.user.id,grant:first,used:1,iat:now,exp:now+600};
 const message=encode(JSON.stringify({alg:'RS256',typ:'JWT'}))+'.'+encode(JSON.stringify(receiptClaims));const receipt=message+'.'+encode(await crypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(message)));
 assert.equal((await browser.req('/api/ai/receipt',{receipt})).status,200);assert.equal((await browser.req('/api/account')).data.officialAI.remaining,4);
 assert.equal((await browser.req('/api/ai/receipt',{receipt})).status,200);assert.equal((await browser.req('/api/account')).data.officialAI.remaining,4);f.sqlite.close();
});

test('paid AI months renew only at period expiry, not at account refresh or prepayment',async()=>{
 const f=fixture(),owner=f.browser(),buyer=f.browser();await f.register(owner,'owner@example.com');await f.register(buyer,'paid-direct@example.com');f.env.AI_DIRECT_ENABLED=true;f.env.OFFICIAL_AI_READY=true;
 await owner.req('/api/admin/membership',{email:'paid-direct@example.com',plan:'lite',days:60,receipt:'manual-prepaid-60',confirmed:true});
 const first=(await buyer.req('/api/account')).data;assert.equal(first.officialAI.limit,100);assert.ok(first.officialAI.expires<=Date.now()+30*86400000+1000);
 f.sqlite.exec('UPDATE ai_entitlements SET used=10');
 const again=(await buyer.req('/api/account')).data;assert.equal(again.officialAI.remaining,90);assert.equal(again.officialAI.expires,first.officialAI.expires);
 f.sqlite.exec('UPDATE ai_entitlements SET expires=0');const renewed=(await buyer.req('/api/account')).data;assert.equal(renewed.officialAI.remaining,100);f.sqlite.close();
});

test('manual membership requires admin confirmation, deduplicates receipts and expires',async()=>{
 const f=fixture(),owner=f.browser(),user=f.browser();await f.register(owner,'owner@example.com');await f.register(user,'buyer@example.com');
 const body={email:'buyer@example.com',plan:'lite',days:30,receipt:'wx-receipt-001',confirmed:true};
 assert.equal((await user.req('/api/admin/membership',body)).status,403);
 assert.equal((await owner.req('/api/admin/membership',{...body,confirmed:false})).status,400);
 assert.equal((await owner.req('/api/admin/membership',body)).status,200);
 assert.equal((await user.req('/api/account')).data.user.plan,'lite');
 const expiry=f.sqlite.prepare('SELECT expires FROM manual_memberships').get().expires;
 assert.equal((await owner.req('/api/admin/membership',body)).status,200);
 assert.equal(f.sqlite.prepare('SELECT expires FROM manual_memberships').get().expires,expiry);
 assert.equal((await owner.req('/api/admin/membership',{...body,plan:'standard'})).status,409);
 f.sqlite.exec('UPDATE manual_memberships SET expires=0');
 assert.equal((await user.req('/api/account')).data.user.plan,'free');
 assert.equal(f.sqlite.prepare('SELECT COUNT(*) n FROM membership_audit').get().n,1);f.sqlite.close();
});

test('personal QR orders keep server prices and need a verified administrator receipt',async()=>{
 const f=fixture(),owner=f.browser(),user=f.browser(),other=f.browser();await f.register(owner,'owner@example.com');await f.register(user,'buyer@example.com');await f.register(other,'other@example.com');f.env.MANUAL_PAYMENTS_ENABLED=true;
 const created=await user.req('/api/payments/manual/orders',{plan:'standard',cycle:'monthly',amount_cents:1});assert.equal(created.status,201);const o=created.data.order;assert.equal(o.amount_cents,999);
 assert.equal((await user.req('/api/payments/manual/orders',{plan:'standard',cycle:'monthly'})).data.order.id,o.id);
 assert.equal((await user.req('/api/payments/manual/orders',{plan:'lite',cycle:'annual'})).status,400);
 assert.equal((await other.req('/api/payments/manual/receipt',{orderId:o.id,receipt:'wx-paid-001',accountName:'测试账户'})).status,404);
 assert.equal((await user.req('/api/payments/manual/receipt',{orderId:o.id,receipt:'wx-paid-001',accountName:'测试账户'})).status,200);
 assert.equal((await user.req('/api/account')).data.user.plan,'free');
 const approval={orderId:o.id,plan:'standard',days:30,receipt:'wx-paid-001',confirmed:true};
 assert.equal((await user.req('/api/admin/membership',approval)).status,403);
 assert.equal((await owner.req('/api/admin/membership',approval)).status,200);
 assert.equal((await user.req('/api/account')).data.user.plan,'standard');
 assert.equal((await owner.req('/api/admin/membership',approval)).status,200);
 assert.equal(f.sqlite.prepare('SELECT COUNT(*) n FROM membership_audit').get().n,1);
 assert.equal((await user.req('/api/payments/manual/orders')).data.orders[0].status,'approved');f.sqlite.close();
});

test('native mailbox login is bound to device, single use and revocable',async()=>{
 const f=fixture(),browser=f.browser();await f.register(browser,'native@example.com');f.env.NATIVE_LOGIN_ENABLED=true;f.sqlite.exec('DELETE FROM rate_limits');
 const start=(await browser.req('/api/device/start',{name:'Native'})).data;
 const body={email:'native@example.com',deviceCode:start.deviceCode};
 assert.equal((await browser.req('/api/native/send-code',body)).status,200);
 const code=f.mails.at(-1).code;
 const wrong=(await browser.req('/api/device/start',{name:'Other'})).data;
 assert.equal((await browser.req('/api/native/verify',{...body,deviceCode:wrong.deviceCode,code})).status,400);
 const signed=await browser.req('/api/native/verify',{...body,code});assert.equal(signed.status,200);
 assert.equal((await browser.req('/api/native/verify',{...body,code})).status,410);
 const r=await f.worker.fetch(new Request(f.env.APP_ORIGIN+'/api/account',{headers:{Authorization:'Bearer '+signed.data.accessToken}}),f.env);assert.equal(r.status,200);
 await browser.req('/api/account/device',{id:signed.data.deviceId},'DELETE');
 const denied=await f.worker.fetch(new Request(f.env.APP_ORIGIN+'/api/account',{headers:{Authorization:'Bearer '+signed.data.accessToken}}),f.env);assert.equal(denied.status,401);f.sqlite.close();
});

test('native login stops after five wrong codes and does not enumerate new emails',async()=>{
 const f=fixture(),browser=f.browser();await f.register(browser,'native@example.com');f.env.NATIVE_LOGIN_ENABLED=true;f.sqlite.exec('DELETE FROM rate_limits');
 const start=(await browser.req('/api/device/start',{})).data,body={email:'native@example.com',deviceCode:start.deviceCode};
 assert.equal((await browser.req('/api/native/send-code',body)).status,200);const code=f.mails.at(-1).code;
 const wrong=code==='000000'?'111111':'000000';
 for(let i=0;i<5;i++)assert.equal((await browser.req('/api/native/verify',{...body,code:wrong})).status,400);
 assert.equal((await browser.req('/api/native/verify',{...body,code})).status,400);
 const n=f.mails.length;
 assert.equal((await browser.req('/api/native/send-code',{...body,email:'unknown@example.com'})).status,200);
 assert.equal(f.mails.length,n);f.sqlite.close();
});

function fixture() {
  const sqlite = new DatabaseSync(':memory:'); sqlite.exec(readFileSync(new URL('./schema.sql', import.meta.url), 'utf8'));
  sqlite.exec(readFileSync(new URL('./migrations/0001_desktop.sql',import.meta.url),'utf8'));
  sqlite.exec(readFileSync(new URL('./migrations/0002_storage_bridge.sql',import.meta.url),'utf8'));
  sqlite.exec(readFileSync(new URL('./migrations/0003_record_sync.sql',import.meta.url),'utf8'));
  sqlite.exec(readFileSync(new URL('./migrations/0004_manual_membership.sql',import.meta.url),'utf8'));
  sqlite.exec(readFileSync(new URL('./migrations/0005_cloud_usage.sql',import.meta.url),'utf8'));
  const DB = { prepare(sql) { return { bind(...args) { const stmt = sqlite.prepare(sql); return { async first() { return stmt.get(...args) || null; }, async all() { return { results: stmt.all(...args) }; }, async run() { return { meta: { changes: stmt.run(...args).changes } }; } }; } }; } };
  const env = { DB, APP_ORIGIN: 'https://example.com', ADMIN_EMAIL: 'owner@example.com', TURNSTILE_SECRET: 'test', TURNSTILE_SITE_KEY: 'test', AUTH_SECRET: 'random-test-secret-not-production', SMTP_USER: 'test@example.com', SMTP_PASSWORD: 'test' };
  DB.batch=async statements=>{const result=[];for(const s of statements)result.push(await s.run());return result;};
  const mails = [], worker = createWorker({ sendCode: async (_, email, code) => { mails.push({ email, code }); }, verify: async (_, body) => body.turnstileToken === 'valid' });
  function browser(ip = crypto.randomUUID()) {
    const jar = new Map(); let csrf = '';
    return { async req(path, body, method = body ? 'POST' : 'GET', options = {}) {
      const response = await worker.fetch(new Request(env.APP_ORIGIN + path, { method, headers: { 'CF-Connecting-IP': ip, 'Content-Type': 'application/json', 'Origin': options.origin || env.APP_ORIGIN, 'X-FlowTodo-Request': '1', 'X-CSRF-Token': options.csrf ?? csrf, Cookie: [...jar].map(([k,v]) => `${k}=${v}`).join('; ') }, body: body ? JSON.stringify(body) : undefined }), env);
      for (const cookie of response.headers.getSetCookie()) { const [key, value] = cookie.split(';')[0].split('='); jar.set(key, value); }
      const data = await response.json(); if (data.csrf) csrf = data.csrf; return { status: response.status, data, response };
    } };
  }
  async function register(client, email) {
    assert.equal((await client.req('/api/auth/send-code', { email, purpose: 'register', turnstileToken: 'valid' })).status, 200);
    const result = await client.req('/api/auth/register', { email, code: mails.at(-1).code, name: '测试账户', acceptTerms: true }); assert.equal(result.status, 200); return result;
  }
  return { sqlite, env, worker, mails, browser, register };
}

test('outbound bridge requires HMAC, rejects replay and only exchanges ciphertext',async()=>{
 const f=fixture();f.env.STORAGE_KEY='01'.repeat(32);f.env.STORAGE_MODE='reverse';
 async function request(path,body,secret=f.env.STORAGE_KEY){
  const raw=JSON.stringify(body),key=await crypto.subtle.importKey('raw',Uint8Array.from(secret.match(/../g),h=>parseInt(h,16)),{name:'HMAC',hash:'SHA-256'},false,['sign']);
  const mac=Array.from(new Uint8Array(await crypto.subtle.sign('HMAC',key,new TextEncoder().encode('flowtodo-storage-bridge-v1\n'+path+'\n'+raw))),b=>b.toString(16).padStart(2,'0')).join('');
  return f.worker.fetch(new Request(f.env.APP_ORIGIN+path,{method:'POST',headers:{'X-FlowTodo-Bridge':mac},body:raw}),f.env);
 }
 const id=crypto.randomUUID(),envelope={nonce:'randomnonce',data:'encryptedrecord'};
 const pending=bridgeExchange(f.env,id,envelope,'records',2000);
 const body={nonce:crypto.randomUUID(),at:Date.now(),kind:'records'};
 const path='/api/storage/bridge/poll';
 assert.equal((await request(path,body,'02'.repeat(32))).status,403);
 const result=await request(path,body);assert.equal(result.status,200);
 const job=await result.json();assert.deepEqual(job,{id,envelope});
 assert.equal((await request(path,body)).status,503);
 const answer={nonce:'resultnonce',data:'encryptedanswer'};
 assert.equal((await request('/api/storage/bridge/result',{nonce:crypto.randomUUID(),at:Date.now(),id,envelope:answer})).status,200);
 assert.deepEqual(await (await pending).json(),answer);
 assert.equal(f.sqlite.prepare('SELECT count(*) AS n FROM storage_bridge_jobs').get().n,0);f.sqlite.close();
});

test('desktop upload acknowledgement loss does not duplicate a cloud record',async()=>{
 const f=fixture(),client=f.browser();await f.register(client,'sync@example.com');
 const body={kind:'tasks',title:'同一条记录',payload:{_syncUid:crypto.randomUUID().replaceAll('-',''),record:{done:false}}};
 const first=await client.req('/api/cloud/items',body),second=await client.req('/api/cloud/items',body);
 assert.equal(first.status,201);assert.equal(second.status,201);assert.equal(first.data.item.id,second.data.item.id);
 assert.equal((await client.req('/api/account')).data.usage.tasks,1);f.sqlite.close();
});
test('desktop connection requires explicit browser approval and can be revoked', async()=>{
 const f=fixture(),browser=f.browser();await f.register(browser,'desktop@example.com');
 async function desktop(path,body,token){const response=await f.worker.fetch(new Request(f.env.APP_ORIGIN+path,{method:body?'POST':'GET',headers:{Origin:f.env.APP_ORIGIN,'Content-Type':'application/json','X-FlowTodo-Request':'1',...(token?{Authorization:'Bearer '+token}:{})},body:body?JSON.stringify(body):undefined}),f.env);return {status:response.status,data:await response.json()};}
 const start=(await desktop('/api/device/start',{name:'测试电脑'})).data;
 assert.equal((await desktop('/api/device/poll',{deviceCode:start.deviceCode})).status,202);
 assert.equal((await browser.req('/api/device/authorize',{userCode:start.userCode})).data.name,'测试电脑');
 assert.equal((await desktop('/api/device/poll',{deviceCode:start.deviceCode})).status,202);
 await browser.req('/api/device/authorize',{userCode:start.userCode,confirm:true});const connected=await desktop('/api/device/poll',{deviceCode:start.deviceCode});assert.equal(connected.status,200);
 assert.equal((await desktop('/api/account',undefined,connected.data.accessToken)).status,200);
 assert.equal((await desktop('/api/device/poll',{deviceCode:start.deviceCode})).status,410);
 await browser.req('/api/account/device',{id:connected.data.deviceId},'DELETE');assert.equal((await desktop('/api/account',undefined,connected.data.accessToken)).status,401);f.sqlite.close();
});

test('avatar revisions protect another device update and reject SVG',async()=>{
 const f=fixture(),browser=f.browser();await f.register(browser,'avatar@example.com');
 assert.equal((await browser.req('/api/account/avatar',{data:'data:image/svg+xml;base64,PHN2Zz4=',revision:0},'PUT')).status,400);
 assert.equal((await browser.req('/api/account/avatar',{data:'',revision:0},'PUT')).status,200);
 assert.equal((await browser.req('/api/account/avatar',{data:'',revision:0},'PUT')).status,409);
 assert.equal((await browser.req('/api/account/avatar')).data.revision,1);f.sqlite.close();
});

test('registration requires CAPTCHA and cannot set plan, role or balance', async () => {
  const f = fixture(), client = f.browser();
  assert.equal((await client.req('/api/auth/send-code', { email: 'a@example.com', purpose: 'register' })).status, 400);
  await client.req('/api/auth/send-code', { email: 'a@example.com', purpose: 'register', turnstileToken: 'valid' });
  const result = await client.req('/api/auth/register', { email: 'a@example.com', code: f.mails.at(-1).code, name: 'A', acceptTerms: true, role: 'admin', plan: 'standard', balance: 999 });
  assert.equal(result.status, 200); assert.equal(result.data.user.role, 'user'); assert.equal(result.data.user.plan, 'free'); assert.equal(result.data.user.balance, 0);
  assert.match(result.response.headers.getSetCookie().join(';'), /HttpOnly; Secure; SameSite=Strict/); f.sqlite.close();
});
test('email codes bind browser and purpose, expire, and cannot be reused', async () => {
  const f = fixture(), a = f.browser(), b = f.browser(), email = 'a@example.com';
  await a.req('/api/auth/send-code', { email, purpose: 'register', turnstileToken: 'valid' }); const code = f.mails.at(-1).code;
  assert.equal((await b.req('/api/auth/register', { email, code, name: 'A', acceptTerms: true })).status, 400);
  assert.equal((await a.req('/api/auth/login', { email, code })).status, 400);
  assert.equal((await a.req('/api/auth/register', { email, code, name: 'A', acceptTerms: true })).status, 200);
  assert.equal((await a.req('/api/auth/register', { email, code, name: 'A', acceptTerms: true })).status, 400);
  await b.req('/api/auth/send-code', { email: 'b@example.com', purpose: 'register', turnstileToken: 'valid' }); f.sqlite.exec('UPDATE codes SET expires=0');
  assert.equal((await b.req('/api/auth/register', { email: 'b@example.com', code: f.mails.at(-1).code, name: 'B', acceptTerms: true })).status, 400); f.sqlite.close();
});
test('five wrong attempts lock a code and mail cooldown prevents flooding', async () => {
  const f = fixture(), a = f.browser(), email = 'a@example.com';
  await a.req('/api/auth/send-code', { email, purpose: 'register', turnstileToken: 'valid' }); const code = f.mails.at(-1).code;
  assert.equal((await a.req('/api/auth/send-code', { email, purpose: 'register', turnstileToken: 'valid' })).status, 429);
  for (let i=0;i<5;i++) await a.req('/api/auth/register', { email, code: code === '000000' ? '111111' : '000000', name: 'A', acceptTerms: true });
  assert.equal((await a.req('/api/auth/register', { email, code, name: 'A', acceptTerms: true })).status, 400); f.sqlite.close();
});
test('cloud records persist and are isolated between users with CSRF checks', async () => {
  const f = fixture(), a = f.browser(), b = f.browser(); await f.register(a,'a@example.com'); await f.register(b,'b@example.com');
  assert.equal((await a.req('/api/cloud/items',{kind:'tasks',title:'私有任务',payload:{}},'POST',{csrf:'wrong'})).status,403);
  const created = await a.req('/api/cloud/items',{kind:'tasks',title:'私有任务',payload:{done:false}}); assert.equal(created.status,201);
  assert.equal((await b.req('/api/cloud/items')).data.items.length,0);
  assert.equal((await b.req('/api/cloud/items/'+created.data.item.id,{version:1},'DELETE')).status,404);
  assert.equal((await a.req('/api/account')).data.usage.tasks,1);
  const exported = await a.req('/api/cloud/export'); assert.equal(exported.data.items[0].title,'私有任务');
  assert.equal((await a.req('/api/account/profile',{name:'Other'},'PATCH',{origin:'https://evil.example'})).status,403); f.sqlite.close();
});
test('quota enforced atomically and restore checks quota; revision prevents overwrite', async () => {
  const f = fixture(), a = f.browser(); await f.register(a,'a@example.com'); let first;
  for(let i=0;i<5;i++) { const result=await a.req('/api/cloud/items',{kind:'flows',title:'Flow '+i,payload:{}}); assert.equal(result.status,201); first ||= result.data.item; }
  assert.equal((await a.req('/api/cloud/items',{kind:'flows',title:'Overflow',payload:{}})).status,409);
  const path='/api/cloud/items/'+first.id;
  assert.equal((await a.req(path,{version:1,title:'Changed',payload:{}},'PATCH')).status,200);
  assert.equal((await a.req(path,{version:1,title:'Stale',payload:{}},'PATCH')).status,409);
  assert.equal((await a.req(path,{version:2},'DELETE')).status,200);
  assert.equal((await a.req('/api/cloud/items?trash=1')).data.items.length,1);
  await a.req('/api/cloud/items',{kind:'flows',title:'Replacement',payload:{}});
  assert.equal((await a.req(path+'/restore',{version:3})).status,409); f.sqlite.close();
});
test('administrator is granted only after owner mailbox verified; users denied', async () => {
  const f = fixture(), a=f.browser(), admin=f.browser(); await f.register(a,'a@example.com'); await f.register(admin,'owner@example.com');
  assert.equal((await a.req('/api/admin/overview')).status,403); const overview=await admin.req('/api/admin/overview'); assert.equal(overview.status,200); assert.equal(overview.data.stats.users,2);
  await a.req('/api/account/sessions',{},'DELETE'); assert.equal((await a.req('/api/account')).status,401); f.sqlite.close();
});
test('missing deployment secrets fail closed without exposing config or local mailbox', async () => {
  const f = fixture(); delete f.env.SMTP_PASSWORD;
  const response=await f.worker.fetch(new Request(f.env.APP_ORIGIN+'/api/config'),f.env); assert.equal((await response.json()).publicPreview,true);
  assert.equal((await f.worker.fetch(new Request(f.env.APP_ORIGIN+'/api/dev/mailbox'),f.env)).status,503); f.sqlite.close();
});
