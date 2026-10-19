import { connect } from 'cloudflare:sockets';
// Credentials are never logged. Only encrypted QQ submission port 465 is used.
export async function sendCode(env, email, code) {
  const socket = connect({ hostname: 'smtp.qq.com', port: 465 }, { secureTransport: 'on' });
  const reader = socket.readable.getReader(), writer = socket.writable.getWriter();
  const encoder = new TextEncoder(), decoder = new TextDecoder();
  let buffer = '';
  const deadline = setTimeout(() => socket.close().catch(() => {}), 15000);
  async function reply(expected) {
    for (let lines = 0; lines < 100; lines++) {
      while (!buffer.includes('\r\n')) {
        const part = await reader.read();
        if (part.done) throw new Error('smtp_closed');
        buffer += decoder.decode(part.value, { stream: true });
        if (buffer.length > 65536) throw new Error('smtp_oversize');
      }
      const index = buffer.indexOf('\r\n'), line = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      if (!/^\d{3}[ -]/.test(line)) throw new Error('smtp_protocol');
      if (line[3] === '-') continue;
      if (!expected.includes(Number(line.slice(0, 3)))) throw new Error('smtp_rejected');
      return;
    }
    throw new Error('smtp_protocol');
  }
  async function command(value, expected) { await writer.write(encoder.encode(value + '\r\n')); await reply(expected); }
  try {
    await socket.opened; await reply([220]);
    await command('EHLO flowtodo.cheemsdoge.xyz', [250]);
    await command('AUTH LOGIN', [334]);
    await command(btoa(env.SMTP_USER), [334]);
    await command(btoa(env.SMTP_PASSWORD), [235]);
    await command(`MAIL FROM:<${env.SMTP_USER}>`, [250]);
    await command(`RCPT TO:<${email}>`, [250, 251]);
    await command('DATA', [354]);
    const body = `FlowTodo 邮箱验证码：${code}\n\n10 分钟内有效。请勿分享验证码。如非本人操作，请忽略。`;
    const encoded = btoa(String.fromCharCode(...encoder.encode(body))).match(/.{1,76}/g).join('\r\n');
    await command(`From: FlowTodo <${env.SMTP_USER}>\r\nTo: <${email}>\r\nSubject: FlowTodo verification code\r\nDate: ${new Date().toUTCString()}\r\nMessage-ID: <${crypto.randomUUID()}@cheemsdoge.xyz>\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n${encoded}\r\n.`, [250]);
    await command('QUIT', [221]).catch(() => {});
  } finally { clearTimeout(deadline); reader.releaseLock(); writer.releaseLock(); await socket.close().catch(() => {}); }
}
