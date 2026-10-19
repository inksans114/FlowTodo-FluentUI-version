"""Private Sub2API adapter. No upstream key, password or JWT leaves this module."""
from __future__ import annotations
import base64
import json
import secrets
import threading
import time
import urllib.error
import urllib.request
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from server_storage import Error, dumps, UUID

_guard=threading.Lock()
_busy=set()
class Relay:
    def __init__(self,config,store):
        self.config,self.store=config,store
        self.vault=AESGCM(bytes.fromhex(config['relayVaultKey']))
    def pack(self,value):
        nonce=secrets.token_bytes(12)
        return base64.b64encode(nonce+self.vault.encrypt(nonce,dumps(value).encode(),b'flowtodo-relay-v1')).decode()
    def unpack(self,value):
        raw=base64.b64decode(value);return json.loads(self.vault.decrypt(raw[:12],raw[12:],b'flowtodo-relay-v1'))
    def api(self,path,body=None,method=None,jwt=None,idempotency=None):
        headers={'Content-Type':'application/json'}
        if idempotency:headers['Idempotency-Key']=idempotency
        if jwt:headers['Authorization']='Bearer '+jwt
        elif path.startswith('/api/v1/admin/'):headers['x-api-key']=self.config['sub2apiAdminKey']
        request=urllib.request.Request('http://127.0.0.1:18080'+path,data=None if body is None else dumps(body).encode(),headers=headers,method=method or ('GET' if body is None else 'POST'))
        try:
            with urllib.request.urlopen(request,timeout=240 if path.startswith('/v1/') else 25) as response:
                data=json.loads(response.read(2_000_001))
        except urllib.error.HTTPError as error:
            # Deliberately do not return provider bodies, headers, or credentials.
            raise Error(503 if error.code>=500 else 502,'官方 AI 服务暂时无法完成请求，请检查订阅或稍后重试。') from None
        except Exception:raise Error(503,'官方 AI 暂时无法连接，请稍后重试。') from None
        if path.startswith('/api/'):
            if data.get('code') not in (0,None):raise Error(502,'中转管理接口暂时无法完成操作。')
            return data.get('data',data)
        return data
    def handle(self,uid,path,body):
        if not UUID.fullmatch(uid):raise Error(400,'账户标识无效。')
        if not self.config.get('sub2apiAdminKey'):raise Error(503,'官方通道正在准备中。')
        with _guard:
            if uid in _busy:raise Error(429,'官方通道一次只处理一个请求，请稍后重试。')
            _busy.add(uid)
        try:
            if path=='/api/ai/provision':return self.provision(uid,body)
            if path=='/api/ai/chat':return self.chat(uid,body)
            raise Error(404,'未找到官方通道功能。')
        finally:
            with _guard:_busy.discard(uid)
    def provision(self,uid,body):
        budget=body.get('budgetUsd');days=body.get('days');grant=body.get('grantId')
        if not isinstance(budget,(int,float)) or not 0<budget<=5 or not isinstance(days,int) or not 1<=days<=366 or not UUID.fullmatch(str(grant or '')):raise Error(400,'额度或授权参数无效。')
        with self.store.connect() as db:
            row=db.execute('SELECT * FROM relay_users WHERE user_id=?',(uid,)).fetchone()
        if row and row['grant_id']==grant and row['status']=='active':return 200,{'provisioned':True,'expires':int(row['expires']*1000)}
        secret=self.unpack(row['secret']) if row else {'email':'flowtodo-'+uid+'@accounts.example.invalid','password':secrets.token_urlsafe(40)}
        if not row:
            with self.store.connect() as db:db.execute('INSERT INTO relay_users(user_id,secret) VALUES(?,?)',(uid,self.pack(secret)))
        if not secret.get('sub2Id'):
            found=self.api('/api/v1/admin/users?page=1&page_size=10&search='+secret['email'])
            users=found.get('items',[]) if isinstance(found,dict) else found
            matched=next((u for u in users if u.get('email')==secret['email']),None)
            created=matched or self.api('/api/v1/admin/users',{'email':secret['email'],'password':secret['password'],'username':'FlowTodo '+uid[:8],'role':'user','balance':0,'concurrency':1,'rpm_limit':5,'allowed_groups':[self.config['sub2apiGroupId']],'restrict_public_groups':True,'notes':'FlowTodo managed account; credentials stay on server'})
            secret['sub2Id']=created['id']
            with self.store.connect() as db:db.execute('UPDATE relay_users SET secret=? WHERE user_id=?',(self.pack(secret),uid))
        jwt=self.api('/api/v1/auth/login',{'email':secret['email'],'password':secret['password']})['access_token']
        if secret.get('keyId') and secret.get('pendingGrant')!=grant:self.api('/api/v1/keys/'+str(secret['keyId']),{'status':'inactive'},'PUT',jwt)
        # This grants relay quota only after the website administrator or verified payment flow authorizes it.
        if secret.get('pendingGrant')!=grant:
            secret.update(pendingGrant=grant,pendingKey='sk-'+secrets.token_hex(24),pendingExpires=time.time()+days*86400)
            with self.store.connect() as db:db.execute("UPDATE relay_users SET secret=?,status='pending' WHERE user_id=?",(self.pack(secret),uid))
            self.api('/api/v1/admin/users/'+str(secret['sub2Id']),{'balance':budget,'concurrency':1,'rpm_limit':5},'PUT')
        found=self.api('/api/v1/keys?page=1&page_size=100&search=FlowTodo',jwt=jwt)
        existing=next((k for k in (found.get('items',[]) if isinstance(found,dict) else found) if k.get('name')=='FlowTodo '+grant[:8]),None)
        key=existing or self.api('/api/v1/keys',{'name':'FlowTodo '+grant[:8],'custom_key':secret['pendingKey'],'group_id':self.config['sub2apiGroupId'],'quota':budget,'expires_in_days':days,'rate_limit_1d':budget,'rate_limit_5h':budget,'rate_limit_7d':budget},jwt=jwt,idempotency=grant)
        secret.update(key=secret['pendingKey'],keyId=key['id'])
        if secret.get('balanceGrant')!=grant:
            self.api('/api/v1/admin/users/'+str(secret['sub2Id'])+'/balance',{'balance':budget,'operation':'set','notes':'FlowTodo capped grant '+grant},idempotency=grant)
            secret['balanceGrant']=grant
        expires=secret['pendingExpires']
        with self.store.connect() as db:db.execute("UPDATE relay_users SET secret=?,grant_id=?,budget=?,expires=?,status='active' WHERE user_id=?",(self.pack(secret),grant,budget,expires,uid))
        return 200,{'provisioned':True,'expires':int(expires*1000)}
    def chat(self,uid,body):
        with self.store.connect() as db:row=db.execute('SELECT * FROM relay_users WHERE user_id=?',(uid,)).fetchone()
        if not row or row['status']!='active' or row['expires']<time.time():raise Error(403,'官方 AI 额度尚未开通或已到期。')
        if not self.config.get('pricingVerified'):raise Error(503,'官方模型价格上限尚未核验，暂不发起付费请求。')
        messages=body.get('messages');limit=body.get('maxTokens',1800)
        if not isinstance(messages,list) or not 1<=len(messages)<=40 or not isinstance(limit,int) or not 1<=limit<=8192:raise Error(400,'对话或输出长度无效。')
        clean=[]
        for item in messages:
            if not isinstance(item,dict) or item.get('role') not in ('system','user','assistant') or not isinstance(item.get('content'),str):raise Error(400,'对话格式无效。')
            clean.append({'role':item['role'],'content':item['content']})
        encoded=len(dumps(clean).encode())
        if encoded>80000:raise Error(413,'对话内容过长，请减少背景内容。')
        secret=self.unpack(row['secret'])
        jwt=self.api('/api/v1/auth/login',{'email':secret['email'],'password':secret['password']})['access_token']
        key=self.api('/api/v1/keys/'+str(secret['keyId']),jwt=jwt)
        maximum=(encoded*self.config['maxInputUsdPerMillion']+limit*self.config['maxOutputUsdPerMillion'])/1_000_000
        if key.get('quota_used',0)+maximum>row['budget']:raise Error(403,'官方 AI 金额额度不足以覆盖本次最大输出，请缩短对话或减少输出长度。')
        # Single-flight per managed user plus an input/output upper-bound check.
        request=urllib.request.Request('http://127.0.0.1:18080/v1/chat/completions',data=dumps({'model':self.config['officialModel'],'messages':clean,'max_tokens':limit,'stream':False,'temperature':min(1,max(0,float(body.get('temperature',0.7))))}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+secret['key']},method='POST')
        try:
            with urllib.request.urlopen(request,timeout=240) as response:data=json.loads(response.read(2_000_001))
            choice=data['choices'][0];content=choice['message']['content']
            if not isinstance(content,str) or not content.strip():raise ValueError('empty')
            content=content.replace(secret['key'],'[已隐藏]')
            usage=data.get('usage') or {};safe_usage={k:v for k,v in usage.items() if k in ('total_tokens','prompt_tokens','completion_tokens') and isinstance(v,int) and v>=0}
            return 200,{'choices':[{'message':{'role':'assistant','content':content},'finish_reason':choice.get('finish_reason','stop')}],'usage':safe_usage}
        except Exception:raise Error(503,'官方 AI 请求失败。调用次数未扣除；中转已发生的上游费用需以中转账单为准。') from None
