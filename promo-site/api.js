import express from 'express';
import { DatabaseSync } from 'node:sqlite';
import { randomBytes, randomInt, createHash, scrypt, timingSafeEqual } from 'node:crypto';
import { promisify } from 'node:util';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import nodemailer from 'nodemailer';
import { PLANS as plans } from './src/plans.js';

const derive = promisify(scrypt);
const digest = value => createHash('sha256').update(value).digest('hex');
const token = () => randomBytes(32).toString('hex');
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export { plans };

export function createApp(options = {}) {
  const production = options.production ?? process.env.NODE_ENV === 'production';
  const origin = options.origin || process.env.APP_ORIGIN || 'http://localhost:4190';
  if (production && (!process.env.SMTP_HOST || !process.env.SMTP_FROM || !process.env.TURNSTILE_SECRET || !process.env.TURNSTILE_SITE_KEY || !origin.startsWith('https://'))) throw new Error('Production requires HTTPS APP_ORIGIN, SMTP_HOST, SMTP_FROM and Turnstile keys.');
  const dataDir = options.dataDir || path.resolve('.data');
  mkdirSync(dataDir, { recursive: true });
  const db = new DatabaseSync(path.join(dataDir, 'accounts.sqlite'));
  db.exec(`PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;
    CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL, plan TEXT NOT NULL DEFAULT 'free', balance_cents INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sessions (hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), csrf TEXT NOT NULL, expires INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS verification (email TEXT NOT NULL, owner TEXT NOT NULL, hash TEXT NOT NULL, expires INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, sent_at INTEGER NOT NULL, PRIMARY KEY(email, owner));
    CREATE TABLE IF NOT EXISTS interests (user_id TEXT NOT NULL REFERENCES users(id), plan TEXT NOT NULL, cycle TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(user_id, plan, cycle));`);
  const app = express();
  app.disable('x-powered-by');
  const captcha = new Map(), rates = new Map(), mailbox = new Map();
  const transport = process.env.SMTP_HOST ? nodemailer.createTransport({ host: process.env.SMTP_HOST, port: Number(process.env.SMTP_PORT || 587), secure: process.env.SMTP_PORT === '465', requireTLS: true, auth: process.env.SMTP_USER ? { user: process.env.SMTP_USER, pass: process.env.SMTP_PASSWORD } : undefined }) : null;
  const cookie = (res, name, value, maxAge) => res.cookie(name, value, { httpOnly: true, secure: production, sameSite: 'strict', path: '/', maxAge });
  const readCookies = req => Object.fromEntries((req.headers.cookie || '').split(';').map(x => x.trim().split('=')).filter(x => x.length === 2));
  const fail = (res, status, message) => res.status(status).json({ error: message });
  function limit(req, res, bucket, max, duration) {
    const key = `${bucket}:${req.ip}`, now = Date.now();
    let entry = rates.get(key);
    if (!entry || entry.until < now) { entry = { count: 0, until: now + duration }; rates.set(key, entry); }
    if (++entry.count > max) { res.set('Retry-After', String(Math.ceil((entry.until - now) / 1000))); fail(res, 429, '请求过于频繁，请稍后重试。'); return false; }
    return true;
  }
  app.use((req, res, next) => {
    res.set({ 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'same-origin', 'X-Frame-Options': 'DENY', 'Permissions-Policy': 'camera=(), microphone=(), geolocation=()', 'Content-Security-Policy': "default-src 'self'; script-src 'self' https://challenges.cloudflare.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; object-src 'none'; base-uri 'self'; frame-ancestors 'none'" });
    if (production) res.set('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
    next();
  });
  app.use('/api', express.json({ limit: '16kb' }));
  app.use('/api', (req, res, next) => {
    res.set('Cache-Control', 'no-store');
    if (!limit(req, res, 'api', 180, 60000)) return;
    if (!['GET', 'HEAD'].includes(req.method)) {
      const allowed = production ? [origin] : [origin, 'http://localhost:4190', 'http://127.0.0.1:4190', 'http://localhost:5173', 'http://127.0.0.1:5173'];
      if (req.headers['x-flowtodo-request'] !== '1' || (req.headers.origin && !allowed.includes(req.headers.origin))) return fail(res, 403, '请求来源校验失败，请刷新页面。');
    }
    const cookies = readCookies(req);
    req.owner = cookies.flowtodo_guest;
    if (!/^[a-f0-9]{64}$/.test(req.owner || '')) { req.owner = token(); cookie(res, 'flowtodo_guest', req.owner, 3600000); }
    req.session = db.prepare('SELECT * FROM sessions WHERE hash = ? AND expires > ?').get(digest(cookies.flowtodo_session || ''), Date.now());
    next();
  });
  function auth(req, res, next) {
    if (!req.session) return fail(res, 401, '请先登录你的账户。');
    if (!['GET', 'HEAD'].includes(req.method) && req.headers['x-csrf-token'] !== req.session.csrf) return fail(res, 403, '安全令牌已失效，请刷新页面。');
    req.user = db.prepare('SELECT * FROM users WHERE id = ?').get(req.session.user_id);
    next();
  }
  const publicUser = u => ({ id: u.id, email: u.email, name: u.name, plan: u.plan, balance: u.balance_cents / 100, createdAt: u.created_at, emailVerified: true });
  let activeKdfs = 0;
  async function passwordHash(password, salt) {
    if (activeKdfs >= 2) throw Object.assign(new Error('认证繁忙'), { status: 503 });
    activeKdfs++;
    try { return (await derive(password, salt, 64, { N: 131072, r: 8, p: 1, maxmem: 256 * 1024 * 1024 })).toString('hex'); }
    finally { activeKdfs--; }
  }
  function createSession(req, res, user) {
    const existing = readCookies(req).flowtodo_session;
    if (existing) db.prepare('DELETE FROM sessions WHERE hash = ?').run(digest(existing));
    const raw = token(), csrf = token();
    db.prepare('INSERT INTO sessions VALUES (?, ?, ?, ?)').run(digest(raw), user.id, csrf, Date.now() + 7 * 86400000);
    cookie(res, 'flowtodo_session', raw, 7 * 86400000);
    return { user: publicUser(user), csrf };
  }
  async function checkCaptcha(req) {
    if (process.env.TURNSTILE_SECRET && !options.captchaAnswer) {
      try {
        const response = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', { method: 'POST', body: new URLSearchParams({ secret: process.env.TURNSTILE_SECRET, response: String(req.body.turnstileToken || ''), remoteip: req.ip }), signal: AbortSignal.timeout(8000) });
        const result = await response.json();
        return result.success === true && result.hostname === new URL(origin).hostname;
      } catch { return false; }
    }
    const record = captcha.get(req.body.captchaId);
    captcha.delete(req.body.captchaId);
    return record && record.owner === req.owner && record.expires > Date.now() && digest(String(req.body.captchaText || '').toUpperCase()) === record.hash;
  }
  app.get('/api/config', (_req, res) => res.json({ local: !production, mailMode: transport ? 'smtp' : 'local-preview', turnstileSiteKey: process.env.TURNSTILE_SITE_KEY || null, paymentsEnabled: false, cloudEnabled: false, plans }));
  app.get('/api/status', (_req, res) => res.json({ ok: true, local: !production, cloudEnabled: false, paymentsEnabled: false }));
  app.get('/api/auth/captcha', (req, res) => {
    if (!limit(req, res, 'captcha', 30, 60000)) return;
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    const answer = options.captchaAnswer || Array.from({ length: 5 }, () => chars[randomInt(chars.length)]).join(''), id = token();
    captcha.set(id, { hash: digest(answer), owner: req.owner, expires: Date.now() + 5 * 60000 });
    const letters = [...answer].map((char, i) => `<text x="${18 + i * 29}" y="${35 + randomInt(8)}" transform="rotate(${randomInt(-15, 16)} ${18 + i * 29} 35)" fill="#${['245ab0', '174777', '49618a'][i % 3]}" font-size="28" font-weight="700" font-family="monospace">${char}</text>`).join('');
    const lines = Array.from({ length: 6 }, () => `<path d="M0 ${randomInt(60)} Q80 ${randomInt(60)} 180 ${randomInt(60)}" fill="none" stroke="#93aecf" opacity=".5"/>`).join('');
    res.json({ id, image: `data:image/svg+xml;base64,${Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="180" height="60"><rect width="180" height="60" rx="8" fill="#eef4fc"/>${letters}${lines}</svg>`).toString('base64')}` });
  });
  app.post('/api/auth/send-code', async (req, res) => {
    if (!limit(req, res, 'send', 8, 3600000)) return;
    const email = String(req.body.email || '').trim().toLowerCase();
    if (email.length > 254 || !emailPattern.test(email)) return fail(res, 400, '请填写有效的邮箱地址。');
    const prior = db.prepare('SELECT * FROM verification WHERE email = ? AND owner = ?').get(email, req.owner);
    if (prior && Date.now() - prior.sent_at < 60000) return fail(res, 429, '请等待 60 秒再重新发送。');
    if (!await checkCaptcha(req)) return fail(res, 400, '图像验证失败或已过期，请重新验证。');
    const code = String(randomInt(100000, 1000000));
    try {
      if (transport) await transport.sendMail({ from: process.env.SMTP_FROM, to: email, subject: 'FlowTodo · 邮箱验证码', text: `你的邮箱验证码是 ${code}，10 分钟内有效。如非本人操作，请忽略。` });
      else if (!production) mailbox.set(`${req.owner}:${email}`, { code, expires: Date.now() + 600000 });
      else return fail(res, 503, '邮件服务尚未配置。');
      db.prepare('INSERT OR REPLACE INTO verification VALUES (?, ?, ?, ?, 0, ?)').run(email, req.owner, digest(`${req.owner}:${email}:${code}`), Date.now() + 600000, Date.now());
      res.json({ sent: true, mode: transport ? 'smtp' : 'local-preview' });
    } catch { return fail(res, 503, '邮件暂时无法发送，请稍后重试。'); }
  });
  app.get('/api/dev/mailbox', (req, res) => {
    if (production || transport) return fail(res, 404, '未找到此功能。');
    const record = mailbox.get(`${req.owner}:${String(req.query.email || '').toLowerCase()}`);
    if (!record || record.expires < Date.now()) return fail(res, 404, '没有有效的本地预览邮件。');
    res.json({ code: record.code, notice: '这封邮件没有发送到互联网，仅用于本地开发验证。' });
  });
  app.post('/api/auth/register', async (req, res) => {
    if (!limit(req, res, 'register', 10, 3600000)) return;
    const email = String(req.body.email || '').trim().toLowerCase(), password = req.body.password, name = String(req.body.name || '').trim();
    if (!emailPattern.test(email) || email.length > 254) return fail(res, 400, '请填写有效的邮箱地址。');
    if (typeof password !== 'string' || [...password].length < 15 || [...password].length > 128 || Buffer.byteLength(password) > 512) return fail(res, 400, '密码需要 15–128 个字符，建议使用多个词组成的口令。');
    if (!name || name.length > 40) return fail(res, 400, '昵称需要 1–40 个字符。');
    if (req.body.acceptTerms !== true) return fail(res, 400, '请阅读并同意服务条款与隐私说明。');
    const record = db.prepare('SELECT * FROM verification WHERE email = ? AND owner = ?').get(email, req.owner);
    if (!record || record.expires < Date.now() || record.attempts >= 5) return fail(res, 400, '请重新获取邮箱验证码。');
    db.prepare('UPDATE verification SET attempts = attempts + 1 WHERE email = ? AND owner = ?').run(email, req.owner);
    if (digest(`${req.owner}:${email}:${String(req.body.code || '')}`) !== record.hash) return fail(res, 400, '邮箱验证码不正确。');
    // Consume before awaiting the KDF, so concurrent requests cannot replay verification.
    db.prepare('DELETE FROM verification WHERE email = ? AND owner = ?').run(email, req.owner);
    mailbox.delete(`${req.owner}:${email}`);
    if (db.prepare('SELECT id FROM users WHERE email = ?').get(email)) return fail(res, 409, '此邮箱已注册，请登录。');
    const salt = randomBytes(16).toString('hex'), hash = await passwordHash(password, salt), id = token().slice(0, 24);
    try { db.prepare('INSERT INTO users (id, email, name, salt, password_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)').run(id, email, name, salt, hash, new Date().toISOString()); }
    catch { return fail(res, 409, '此邮箱已注册，请登录。'); }
    res.status(201).json(createSession(req, res, db.prepare('SELECT * FROM users WHERE id = ?').get(id)));
  });
  app.post('/api/auth/login', async (req, res) => {
    if (!limit(req, res, 'login', 10, 15 * 60000)) return;
    const email = String(req.body.email || '').trim().toLowerCase(), password = req.body.password;
    if (typeof password !== 'string' || Buffer.byteLength(password) > 512) return fail(res, 400, '邮箱或密码不正确。');
    const user = db.prepare('SELECT * FROM users WHERE email = ?').get(email), hash = await passwordHash(password, user?.salt || 'flowtodo-dummy-timing-salt');
    if (!user || !timingSafeEqual(Buffer.from(hash, 'hex'), Buffer.from(user.password_hash, 'hex'))) return fail(res, 401, '邮箱或密码不正确。');
    res.json(createSession(req, res, user));
  });
  app.get('/api/account', auth, (req, res) => res.json({ user: publicUser(req.user), csrf: req.session.csrf, usage: { tasks: 0, flows: 0, aiPlans: 0, storageMB: 0, aiCalls: 0 }, cloud: { connected: false, items: [] }, transactions: [], interests: db.prepare('SELECT plan, cycle, created_at FROM interests WHERE user_id = ?').all(req.user.id) }));
  app.patch('/api/account/profile', auth, (req, res) => {
    const name = String(req.body.name || '').trim();
    if (!name || name.length > 40) return fail(res, 400, '昵称需要 1–40 个字符。');
    db.prepare('UPDATE users SET name = ? WHERE id = ?').run(name, req.user.id);
    res.json({ user: publicUser(db.prepare('SELECT * FROM users WHERE id = ?').get(req.user.id)) });
  });
  app.post('/api/account/password', auth, async (req, res) => {
    if (!limit(req, res, 'password', 5, 15 * 60000)) return;
    const { currentPassword, password } = req.body;
    if (typeof currentPassword !== 'string' || Buffer.byteLength(currentPassword) > 512 || typeof password !== 'string' || [...password].length < 15 || [...password].length > 128 || Buffer.byteLength(password) > 512) return fail(res, 400, '新密码需要 15–128 个字符。');
    const hash = await passwordHash(currentPassword, req.user.salt);
    if (!timingSafeEqual(Buffer.from(hash, 'hex'), Buffer.from(req.user.password_hash, 'hex'))) return fail(res, 400, '当前密码不正确。');
    const salt = randomBytes(16).toString('hex'), nextHash = await passwordHash(password, salt);
    db.prepare('UPDATE users SET salt = ?, password_hash = ? WHERE id = ?').run(salt, nextHash, req.user.id);
    db.prepare('DELETE FROM sessions WHERE user_id = ?').run(req.user.id);
    cookie(res, 'flowtodo_session', '', 0); res.json({ changed: true });
  });
  app.post('/api/auth/logout', auth, (req, res) => { db.prepare('DELETE FROM sessions WHERE hash = ?').run(req.session.hash); cookie(res, 'flowtodo_session', '', 0); res.json({ ok: true }); });
  app.post('/api/membership/interest', auth, (req, res) => {
    if (!['lite', 'standard'].includes(req.body.plan) || !['monthly', 'annual'].includes(req.body.cycle)) return fail(res, 400, '请选择有效套餐。');
    db.prepare('INSERT OR REPLACE INTO interests VALUES (?, ?, ?, ?)').run(req.user.id, req.body.plan, req.body.cycle, new Date().toISOString());
    res.json({ saved: true, charged: false, message: '意向已保存，未扣款。正式上线后可在会员中心查看。' });
  });
  app.post('/api/payments/checkout', auth, (_req, res) => fail(res, 503, '支付尚未开放，不会扣款或更改会员。'));
  app.use('/api', (_req, res) => fail(res, 404, '未找到接口。'));
  const publicDir = options.publicDir || path.resolve(process.env.PUBLIC_DIR || 'dist');
  app.use(express.static(publicDir));
  app.use((req, res) => { if (req.method !== 'GET') return res.sendStatus(404); res.sendFile(path.join(publicDir, 'index.html')); });
  app.use((error, _req, res, _next) => { const status = [413, 503].includes(error.status) ? error.status : error instanceof SyntaxError ? 400 : 500; res.status(status).json({ error: status === 503 ? '认证服务繁忙，请稍后重试。' : status === 500 ? '服务暂时不可用，请稍后重试。' : '请求格式无效或内容过长。' }); });
  const cleanup = setInterval(() => {
    const now = Date.now();
    for (const [key, value] of captcha) if (value.expires < now) captcha.delete(key);
    for (const [key, value] of mailbox) if (value.expires < now) mailbox.delete(key);
    for (const [key, value] of rates) if (value.until < now) rates.delete(key);
    db.prepare('DELETE FROM sessions WHERE expires < ?').run(now); db.prepare('DELETE FROM verification WHERE expires < ?').run(now);
  }, 60000);
  cleanup.unref();
  return { app, db, close: () => { clearInterval(cleanup); db.close(); } };
}
