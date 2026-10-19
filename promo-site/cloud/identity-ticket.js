// Cloudflare proves mailbox ownership. Subscription authority belongs to Xiangyang.
const encode = value => btoa(String.fromCharCode(...new Uint8Array(value))).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');
const bytes = value => new TextEncoder().encode(value);
export async function issueIdentityTicket(env, identity, now = Date.now()) {
  const origin = new URL(env.IDENTITY_ORIGIN);
  if (origin.protocol !== 'https:' || origin.username || origin.password || origin.pathname !== '/' || origin.search || origin.hash) throw new Error('Invalid identity destination');
  const raw = Uint8Array.from(atob(env.IDENTITY_SIGNING_PKCS8), c => c.charCodeAt(0));
  const key = await crypto.subtle.importKey('pkcs8', raw, {name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'}, false, ['sign']);
  const header = encode(bytes(JSON.stringify({alg:'RS256',typ:'JWT',kid:env.IDENTITY_KEY_ID})));
  if (!/^[a-f0-9]{64}$/.test(identity.state||'')) throw new Error('Invalid login state');
  const claims = {iss:env.APP_ORIGIN,aud:origin.origin,purpose:'mailbox-login',email:identity.email,name:identity.name||'',state:identity.state,iat:Math.floor(now/1000),exp:Math.floor(now/1000)+120,jti:crypto.randomUUID()};
  const payload = encode(bytes(JSON.stringify(claims))), message = header+'.'+payload;
  const signature = await crypto.subtle.sign('RSASSA-PKCS1-v1_5',key,bytes(message));
  return {ticket:message+'.'+encode(signature),origin:origin.origin,expiresIn:120};
}
