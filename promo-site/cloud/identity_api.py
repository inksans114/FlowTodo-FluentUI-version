"""Account and storage API for direct browser/desktop access to Xiangyang."""
import hashlib
import secrets
import time
from datetime import datetime,timezone
from urllib.parse import urlsplit
from uuid import uuid4
from identity_auth import IdentityAuth
from native_login import NativeLogin
from billing import Billing,WechatReceipt
from server_storage import Error

class IdentityAPI:
    def __init__(self,config,store):
        self.config,self.store=config,store
        self.auth=IdentityAuth(config,store)
        with store.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS account_devices(hash TEXT PRIMARY KEY,id TEXT UNIQUE NOT NULL,user_id TEXT NOT NULL,name TEXT NOT NULL,created_at REAL NOT NULL,expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS account_device_requests(hash TEXT PRIMARY KEY,user_code TEXT UNIQUE NOT NULL,name TEXT NOT NULL,expires REAL NOT NULL,user_id TEXT);
            CREATE TABLE IF NOT EXISTS purchase_interests(user_id TEXT NOT NULL,plan TEXT NOT NULL,cycle TEXT NOT NULL,created_at REAL NOT NULL);
            ''')
        self.native=NativeLogin(config,store)
        self.billing=Billing(config,store)

    def payment_notification(self,headers,raw):
        if self.config.get('paymentMode')!='wechat':raise Error(503,'自动支付渠道尚未配置。')
        receipt=WechatReceipt(self.config).verify(headers,raw)
        self.billing.apply(receipt)
        return 200,{'code':'SUCCESS','message':'成功'},{}

    @staticmethod
    def public(row):
        return {'id':row['id'],'email':row['email'],'name':row['name'],'plan':row['plan'],'role':row['role'],'balance':row['balance_cents']/100,'emailVerified':True,'createdAt':datetime.fromtimestamp(row['created_at'],timezone.utc).isoformat()}

    def handle(self,path,method,body,headers):
        route=urlsplit(path).path;origin=self.config['identityOrigin'];write=method not in ('GET','HEAD')
        if write and (headers.get('Origin')!=origin or headers.get('X-FlowTodo-Request')!='1'):raise Error(403,'请求来源校验失败。')
        if route=='/api/config' and method=='GET':
            return 200,{'local':False,'publicPreview':False,'authMode':'external-identity','identityBroker':False,'accountHost':origin,'cloudEnabled':True,'cloudStorageMode':'records','storageLocation':'xiangyang-direct','desktopLoginEnabled':True,'paymentsEnabled':False,'aiEnabled':False,'plans':self.config.get('publicPlans',[])},{}
        if route=='/api/status' and method=='GET':return 200,{'ok':True,'ready':True,'cloudEnabled':True,'paymentsEnabled':False},{}
        if route in ('/api/native/send-code','/api/native/verify') and method=='POST':
            if not self.config.get('smtpUser') or not self.config.get('smtpPassword'):raise Error(503,'软件内邮箱登录暂未启用。')
            return self.native.handle(route,body,headers.get('X-Real-IP','unknown'))
        if route=='/api/identity/start' and method=='POST':
            state=secrets.token_hex(32)
            return 200,{'state':state,'issuer':self.config['identityIssuer']},{'Set-Cookie':'flowtodo_login_state='+state+'; Path=/api/identity/; HttpOnly; Secure; SameSite=Lax; Max-Age=300'}
        if route=='/api/identity/exchange' and method=='POST':
            cookies=dict(x.strip().split('=',1) for x in headers.get('Cookie','').split(';') if '=' in x)
            claims=self.auth.verify(body.get('ticket'))
            state=cookies.get('flowtodo_login_state','')
            if len(state)!=64 or not secrets.compare_digest(state,claims.get('state','')):raise Error(401,'登录验证流程已失效，请重新开始。')
            raw,csrf,user=self.auth.exchange(body.get('ticket'))
            return 200,{'user':self.public(user),'csrf':csrf},{'Set-Cookie':'flowtodo_session='+raw+'; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=604800'}
        if route=='/api/device/start' and method=='POST':
            raw=secrets.token_hex(32);code=secrets.token_hex(5).upper();now=time.time()
            with self.store.connect() as db:
                db.execute('DELETE FROM account_device_requests WHERE expires<?',(now,))
                if db.execute('SELECT count(*) FROM account_device_requests').fetchone()[0]>=1000:raise Error(429,'登录请求较多，请稍后重试。')
                db.execute('INSERT INTO account_device_requests VALUES(?,?,?,?,NULL)',(hashlib.sha256(raw.encode()).hexdigest(),code,str(body.get('name','FlowTodo 桌面端'))[:80],now+300))
            return 200,{'deviceCode':raw,'userCode':code,'verificationUri':origin+'/connect?code='+code,'expiresIn':300,'interval':5},{}
        if route=='/api/device/poll' and method=='POST':
            code=body.get('deviceCode','')
            if not isinstance(code,str) or len(code)!=64:raise Error(400,'登录请求无效。')
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                key=hashlib.sha256(code.encode()).hexdigest();row=db.execute('SELECT * FROM account_device_requests WHERE hash=? AND expires>?',(key,time.time())).fetchone()
                if not row:raise Error(410,'登录请求已到期或已使用。')
                if not row['user_id']:return 202,{'pending':True},{}
                db.execute('DELETE FROM account_device_requests WHERE hash=?',(key,))
                raw=secrets.token_hex(32);id=str(uuid4());expires=time.time()+30*86400
                db.execute('INSERT INTO account_devices VALUES(?,?,?,?,?,?)',(hashlib.sha256(raw.encode()).hexdigest(),id,row['user_id'],row['name'],time.time(),expires))
            return 200,{'accessToken':raw,'deviceId':id,'expiresAt':int(expires*1000)},{}
        bearer=headers.get('Authorization','');device=bearer.startswith('Bearer ')
        if device:
            raw=bearer[7:]
            if len(raw)!=64:raise Error(401,'请先登录。')
            with self.store.connect() as db:
                row=db.execute('SELECT a.*,d.hash,d.id AS device_id FROM accounts a JOIN account_devices d ON a.id=d.user_id WHERE d.hash=? AND d.expires>?',(hashlib.sha256(raw.encode()).hexdigest(),time.time())).fetchone()
            if not row:raise Error(401,'登录已失效。')
            user=dict(row)
        else:
            cookies=dict(x.strip().split('=',1) for x in headers.get('Cookie','').split(';') if '=' in x)
            user=self.auth.session(cookies.get('flowtodo_session'))
            if write and route!='/api/auth/logout' and headers.get('X-CSRF-Token')!=user['csrf']:raise Error(403,'请求校验失败。')
        uid=user['id'];extra={}
        if route=='/api/orders' and method=='POST':return 201,{'order':self.billing.create(user,body)},{}
        if route=='/api/orders' and method=='GET':
            with self.store.connect() as db:orders=[dict(row) for row in db.execute('SELECT * FROM orders WHERE user_id=? ORDER BY created DESC LIMIT 50',(uid,))]
            return 200,{'orders':orders},{}
        if route.startswith('/api/orders/') and method=='GET':return 200,{'order':self.billing.get(uid,route.rsplit('/',1)[1])},{}
        if route=='/api/admin/orders' and method=='GET':
            if user['role']!='admin':raise Error(403,'需要管理员权限。')
            with self.store.connect() as db:orders=[dict(row) for row in db.execute('SELECT o.*,a.email FROM orders o JOIN accounts a ON a.id=o.user_id ORDER BY o.created DESC LIMIT 100')]
            return 200,{'orders':orders},{}
        if route=='/api/auth/logout' and method=='POST':
            with self.store.connect() as db:db.execute('DELETE FROM '+('account_devices' if device else 'account_sessions')+' WHERE hash=?',(user['hash'],))
            return 200,{'ok':True},{'Set-Cookie':'flowtodo_session=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0'}
        if route=='/api/device/authorize' and method=='POST':
            if device:raise Error(403,'请在网页中确认设备。')
            with self.store.connect() as db:
                row=db.execute('SELECT * FROM account_device_requests WHERE user_code=? AND expires>? AND user_id IS NULL',(str(body.get('userCode','')),time.time())).fetchone()
                if not row:raise Error(410,'登录请求已到期或已确认。')
                if body.get('confirm') is not True:return 200,{'name':row['name'],'userCode':row['user_code']},{}
                db.execute('UPDATE account_device_requests SET user_id=? WHERE hash=? AND user_id IS NULL',(uid,row['hash']))
            return 200,{'approved':True},{}
        if route=='/api/account/devices' and method=='GET':
            with self.store.connect() as db:rows=db.execute('SELECT id,name,created_at,expires FROM account_devices WHERE user_id=? AND expires>?',(uid,time.time())).fetchall()
            return 200,{'devices':[dict(row) for row in rows]},{}
        if route=='/api/account/device' and method=='DELETE':
            with self.store.connect() as db:db.execute('DELETE FROM account_devices WHERE user_id=? AND id=?',(uid,str(body.get('id',''))))
            return 200,{'ok':True},{}
        if route=='/api/account/sessions' and method=='DELETE':
            with self.store.connect() as db:
                db.execute('DELETE FROM account_devices WHERE user_id=?',(uid,));db.execute('DELETE FROM account_sessions WHERE user_id=?',(uid,))
            return 200,{'ok':True},{'Set-Cookie':'flowtodo_session=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0'}
        if route=='/api/account/profile' and method=='PATCH':
            name=str(body.get('name','')).strip()
            if not name or len(name)>40:raise Error(400,'昵称需要 1–40 个字符。')
            with self.store.connect() as db:db.execute('UPDATE accounts SET name=? WHERE id=?',(name,uid))
            user['name']=name;return 200,{'user':self.public(user)},{}
        if route=='/api/account' and method=='GET':
            _,summary=self.store.handle(uid,user['plan'],'/api/cloud/summary','GET',{})
            summary['cloud']['location']='xiangyang-direct'
            with self.store.connect() as db:interests=[dict(r) for r in db.execute('SELECT plan,cycle,created_at FROM purchase_interests WHERE user_id=?',(uid,))]
            return 200,{'user':{**self.public(user),'avatarUrl':summary['avatar']['data']},'csrf':user.get('csrf'),**summary,'officialAI':{'connected':False,'active':False,'remaining':0,'limit':0,'used':0},'transactions':[],'interests':interests},{}
        if route=='/api/membership/interest' and method=='POST':
            if body.get('plan') not in ('lite','standard') or body.get('cycle') not in ('monthly','annual'):raise Error(400,'请选择有效方案。')
            with self.store.connect() as db:
                db.execute('DELETE FROM purchase_interests WHERE user_id=? AND plan=? AND cycle=?',(uid,body['plan'],body['cycle']))
                db.execute('INSERT INTO purchase_interests VALUES(?,?,?,?)',(uid,body['plan'],body['cycle'],time.time()))
            return 200,{'message':'升级意向已保存，未扣款。'},{}
        if route.startswith('/api/cloud/') or route=='/api/account/avatar':
            status,data=self.store.handle(uid,user['plan'],path,method,body);return status,data,{}
        if route=='/api/admin/overview' and method=='GET':
            if user['role']!='admin':raise Error(403,'需要管理员权限。')
            with self.store.connect() as db:
                stats=db.execute('SELECT (SELECT count(*) FROM accounts) users,(SELECT count(*) FROM records WHERE deleted_at IS NULL) records,(SELECT coalesce(sum(bytes),0) FROM records) bytes').fetchone()
                users=db.execute('SELECT * FROM accounts ORDER BY created_at DESC LIMIT 100').fetchall()
            return 200,{'stats':dict(stats),'users':[self.public(row) for row in users]},{}
        if route.startswith('/api/ai/') or route.startswith('/api/admin/ai/') or route.startswith('/api/payments/'):
            raise Error(503,'官方 AI 与真实支付尚未开放。')
        raise Error(404,'未找到此功能。')
