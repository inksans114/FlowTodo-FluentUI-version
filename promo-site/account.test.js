import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createApp } from './api.js';

test('account lifecycle, isolation, server validation and restart persistence', async t => {
  const dataDir = mkdtempSync(path.join(tmpdir(), 'flowtodo-web-test-'));
  let service = createApp({ dataDir, captchaAnswer: 'ABCDE', production: false });
  let server = service.app.listen(0, '127.0.0.1');
  await new Promise(resolve => server.once('listening', resolve));
  let base = `http://127.0.0.1:${server.address().port}`;
  const jar = {};
  async function request(url, body, extra = {}, sessionJar = jar, method = 'POST') {
    const response = await fetch(base + url, { method: body === undefined ? 'GET' : method, headers: { 'Content-Type': 'application/json', 'X-FlowTodo-Request': '1', Cookie: Object.entries(sessionJar).map(([k, v]) => `${k}=${v}`).join('; '), ...extra }, body: body === undefined ? undefined : JSON.stringify(body) });
    for (const raw of response.headers.getSetCookie()) { const [name, value] = raw.split(';')[0].split('='); sessionJar[name] = value; }
    return { status: response.status, data: await response.json(), headers: response.headers };
  }
  const user = { name: '测试探索者', email: 'test@example.com', password: 'a long secure password 2026', acceptTerms: true };
  let csrf, oldCookie;
  try {
    await t.test('anonymous data is private; foreign origins and unverified registration fail', async () => {
      assert.equal((await request('/api/account')).status, 401);
      assert.equal((await request('/api/auth/login', user, { Origin: 'https://evil.example' })).status, 403);
      assert.equal((await request('/api/auth/register', user)).status, 400);
      assert.equal((await request('/api/config')).data.plans[0].tasks, 30);
    });
    await t.test('captcha is one use; mailbox is browser bound; email resend has cooldown', async () => {
      let c = (await request('/api/auth/captcha')).data;
      assert.ok(c.image.startsWith('data:image/svg+xml;base64,'));
      assert.equal((await request('/api/auth/send-code', { email: user.email, captchaId: c.id, captchaText: 'WRONG' })).status, 400);
      assert.equal((await request('/api/auth/send-code', { email: user.email, captchaId: c.id, captchaText: 'ABCDE' })).status, 400);
      c = (await request('/api/auth/captcha')).data;
      assert.equal((await request('/api/auth/send-code', { email: user.email, captchaId: c.id, captchaText: 'ABCDE' })).status, 200);
      assert.equal((await request(`/api/dev/mailbox?email=${user.email}`, undefined, {}, {})).status, 404);
      assert.equal((await request('/api/auth/send-code', { email: user.email })).status, 429);
    });
    await t.test('email verification and password validation are enforced; privilege fields ignored', async () => {
      const code = (await request(`/api/dev/mailbox?email=${user.email}`)).data.code;
      assert.equal((await request('/api/auth/register', { ...user, code, password: 'weak' })).status, 400);
      assert.equal((await request('/api/auth/register', { ...user, code: '000000' })).status, 400);
      const registered = await request('/api/auth/register', { ...user, code, plan: 'standard', balance: 999 });
      assert.equal(registered.status, 201); assert.equal(registered.data.user.plan, 'free'); assert.equal(registered.data.user.balance, 0);
      assert.equal(registered.data.user.password_hash, undefined);
      assert.match(registered.headers.get('set-cookie'), /HttpOnly/i); assert.match(registered.headers.get('set-cookie'), /SameSite=Strict/i);
      csrf = registered.data.csrf; oldCookie = jar.flowtodo_session;
      const stored = service.db.prepare('SELECT * FROM users WHERE email = ?').get(user.email);
      assert.notEqual(stored.password_hash, user.password); assert.equal(stored.password_hash.length, 128);
      assert.equal((await request('/api/auth/register', { ...user, code })).status, 400);
      assert.equal((await request(`/api/dev/mailbox?email=${user.email}`)).status, 404);
    });
    await t.test('CSRF protects profile; membership interest never charges; cloud and bills are empty', async () => {
      assert.equal((await request('/api/account/profile', { name: '改名' }, {}, jar, 'PATCH')).status, 403);
      const updated = await request('/api/account/profile', { name: '新称呼', plan: 'standard' }, { 'X-CSRF-Token': csrf }, jar, 'PATCH');
      assert.equal(updated.status, 200); assert.equal(updated.data.user.name, '新称呼'); assert.equal(updated.data.user.plan, 'free');
      assert.equal((await request('/api/membership/interest', { plan: 'lite', cycle: 'annual' }, { 'X-CSRF-Token': csrf })).data.charged, false);
      assert.equal((await request('/api/payments/checkout', { amount: 999 }, { 'X-CSRF-Token': csrf })).status, 503);
      const account = (await request('/api/account')).data;
      assert.equal(account.cloud.connected, false); assert.deepEqual(account.cloud.items, []); assert.deepEqual(account.transactions, []);
      assert.equal(account.user.balance, 0); assert.equal(account.interests.length, 1);
    });
    await t.test('accounts, sessions and saved interests persist across restart', async () => {
      await new Promise(resolve => server.close(resolve)); service.close();
      service = createApp({ dataDir, captchaAnswer: 'ABCDE', production: false });
      server = service.app.listen(0, '127.0.0.1'); await new Promise(resolve => server.once('listening', resolve));
      base = `http://127.0.0.1:${server.address().port}`;
      const account = (await request('/api/account')).data;
      assert.equal(account.user.name, '新称呼'); assert.equal(account.interests[0].plan, 'lite');
    });
    await t.test('logout invalidates cookie; password update revokes every existing session', async () => {
      assert.equal((await request('/api/auth/logout', {}, { 'X-CSRF-Token': csrf })).status, 200);
      assert.equal((await request('/api/account', undefined, {}, { ...jar, flowtodo_session: oldCookie })).status, 401);
      assert.equal((await request('/api/auth/login', { ...user, password: 'incorrect' })).status, 401);
      const login = await request('/api/auth/login', user); assert.equal(login.status, 200);
      assert.notEqual(jar.flowtodo_session, oldCookie); csrf = login.data.csrf;
      const second = {};
      assert.equal((await request('/api/auth/login', user, {}, second)).status, 200);
      assert.equal((await request('/api/account/password', { currentPassword: user.password, password: 'another long password 2026' }, { 'X-CSRF-Token': csrf })).status, 200);
      assert.equal((await request('/api/account', undefined, {}, second)).status, 401);
      assert.equal((await request('/api/auth/login', user)).status, 401);
      assert.equal((await request('/api/auth/login', { ...user, password: 'another long password 2026' })).status, 200);
    });
    await t.test('email code locks after five wrong attempts and login is rate limited', async () => {
      const email = 'another@example.com', c = (await request('/api/auth/captcha')).data;
      assert.equal((await request('/api/auth/send-code', { email, captchaId: c.id, captchaText: 'ABCDE' })).status, 200);
      const code = (await request(`/api/dev/mailbox?email=${email}`)).data.code;
      for (let i = 0; i < 5; i++) assert.equal((await request('/api/auth/register', { ...user, email, code: '000000' })).status, 400);
      assert.equal((await request('/api/auth/register', { ...user, email, code })).status, 400);
      for (let i = 0; i < 5; i++) await request('/api/auth/login', { ...user, password: 'incorrect' });
      assert.equal((await request('/api/auth/login', user)).status, 429);
    });
  } finally {
    await new Promise(resolve => server.close(resolve)); service.close();
    assert.ok(path.resolve(dataDir).startsWith(path.resolve(tmpdir()) + path.sep));
    rmSync(dataDir, { recursive: true, force: true });
  }
});
test('production refuses insecure configuration', () => assert.throws(() => createApp({ production: true, origin: 'http://localhost' }), /Production requires/));

test('concurrent password KDF work is capped to bound memory use', async () => {
  const dataDir = mkdtempSync(path.join(tmpdir(), 'flowtodo-web-kdf-'));
  const service = createApp({ dataDir, production: false });
  const server = service.app.listen(0, '127.0.0.1');
  await new Promise(resolve => server.once('listening', resolve));
  try {
    const results = await Promise.all(Array.from({ length: 4 }, () => fetch(`http://127.0.0.1:${server.address().port}/api/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-FlowTodo-Request': '1' }, body: JSON.stringify({ email: 'absent@example.com', password: 'not a real credential' }) })));
    assert.ok(results.some(r => r.status === 503));
    assert.ok(results.some(r => r.status === 401));
    assert.ok(results.every(r => [401, 503].includes(r.status)));
  } finally {
    await new Promise(resolve => server.close(resolve)); service.close();
    assert.ok(path.resolve(dataDir).startsWith(path.resolve(tmpdir()) + path.sep));
    rmSync(dataDir, { recursive: true, force: true });
  }
});
