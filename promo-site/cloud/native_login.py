"""Mailbox login for existing accounts, bound to the initiating desktop device."""
import hashlib,hmac,re,secrets,smtplib,ssl,time
from email.message import EmailMessage
from uuid import uuid4
from server_storage import Error

class NativeLogin:
    def __init__(self,config,store,sender=None):
        self.config,self.store,self.sender=config,store,sender or self.send
        with store.connect() as db:db.executescript('''
        CREATE TABLE IF NOT EXISTS native_codes(device TEXT PRIMARY KEY,email TEXT NOT NULL,hash TEXT NOT NULL,expires REAL NOT NULL,attempts INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS native_limits(bucket TEXT PRIMARY KEY,count INTEGER NOT NULL,expires REAL NOT NULL);
        ''')
    def digest(self,device,email,code):
        return hmac.new(self.config['storageKey'].encode(),(device+':'+email+':'+code).encode(),hashlib.sha256).hexdigest()
    def send(self,email,code):
        msg=EmailMessage();msg['From']=self.config['smtpUser'];msg['To']=email;msg['Subject']='FlowTodo 登录验证码'
        msg.set_content('你的登录验证码是 '+code+'，10 分钟内有效。请勿将验证码提供给其他人。')
        with smtplib.SMTP_SSL('smtp.qq.com',465,timeout=12,context=ssl.create_default_context()) as smtp:
            smtp.login(self.config['smtpUser'],self.config['smtpPassword']);smtp.send_message(msg)
    def handle(self,path,body,ip):
        email=str(body.get('email','')).strip().lower();device=body.get('deviceCode','');now=time.time()
        if len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[a-zA-Z]{2,}',email) or not isinstance(device,str) or not re.fullmatch('[a-f0-9]{64}',device):raise Error(400,'请输入有效邮箱。')
        key=hashlib.sha256(device.encode()).hexdigest()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM native_limits WHERE expires<?',(now,));db.execute('DELETE FROM native_codes WHERE expires<?',(now,))
            request=db.execute('SELECT * FROM account_device_requests WHERE hash=? AND expires>? AND user_id IS NULL',(key,now)).fetchone()
            if not request:raise Error(410,'登录请求已到期，请重新开始。')
            buckets=[('verify-ip',ip,30,900)] if path.endswith('/verify') else [('mail-cooldown',email,1,60),('mail-email',email,10,86400),('mail-ip',ip,30,86400),('mail-global','all',200,86400)]
            for name,value,maximum,window in buckets:
                bucket=name+':'+hashlib.sha256(value.encode()).hexdigest()+':'+str(int(now//window))
                row=db.execute('INSERT INTO native_limits VALUES(?,1,?) ON CONFLICT(bucket) DO UPDATE SET count=count+1 RETURNING count',(bucket,now+window*2)).fetchone()
                if row[0]>maximum:raise Error(429,'请求过于频繁，请稍后再试。')
            user=db.execute('SELECT id FROM accounts WHERE email=?',(email,)).fetchone()
            if path.endswith('/send-code'):
                code=str(secrets.randbelow(1000000)).zfill(6)
                if user:db.execute('INSERT INTO native_codes VALUES(?,?,?,?,0) ON CONFLICT(device) DO UPDATE SET email=excluded.email,hash=excluded.hash,expires=excluded.expires,attempts=0',(key,email,self.digest(key,email,code),now+600))
            else:
                code=str(body.get('code',''))
                row=db.execute('SELECT * FROM native_codes WHERE device=? AND email=?',(key,email)).fetchone()
                valid=bool(user and row and row['attempts']<5 and re.fullmatch('[0-9]{6}',code) and hmac.compare_digest(row['hash'],self.digest(key,email,code)))
                if row:db.execute('UPDATE native_codes SET attempts=attempts+1 WHERE device=?',(key,))
                # Commit failed attempts rather than rolling them back with the exception.
                if not valid:db.commit();raise Error(400,'验证码错误或已过期；新用户请先注册。')
                db.execute('DELETE FROM native_codes WHERE device=?',(key,));db.execute('DELETE FROM account_device_requests WHERE hash=?',(key,))
                raw=secrets.token_hex(32);id=str(uuid4());expires=now+30*86400
                db.execute('INSERT INTO account_devices VALUES(?,?,?,?,?,?)',(hashlib.sha256(raw.encode()).hexdigest(),id,user['id'],request['name'],now,expires))
                return 200,{'accessToken':raw,'deviceId':id,'expiresAt':int(expires*1000)},{}
        if user:
            try:self.sender(email,code)
            except Exception:
                with self.store.connect() as db:db.execute('DELETE FROM native_codes WHERE device=?',(key,))
                raise Error(503,'验证码暂时无法发送，请稍后重试。') from None
        return 200,{'message':'如果该邮箱已经注册，验证码将发送至邮箱。'},{}
