"""Private low-price rotation, bounded attempts, and durable monetary reservations."""
import hashlib
import json
import math
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from uuid import UUID as UUIDType
from sub2api_adapter import Relay
from server_storage import Error,dumps
from relay_pricing import price_bounds

class OfficialRelay(Relay):
    def routes(self):
        routes=self.config.get('officialRoutes') or []
        if not routes:raise Error(503,'官方模型轮换正在配置中。')
        return routes

    def save_secret(self,uid,secret):
        with self.store.connect() as db:db.execute('UPDATE relay_users SET secret=? WHERE user_id=?',(self.pack(secret),uid))

    def provision(self,uid,body):
        routes=self.routes()
        # The original provisioner creates one managed user and the first capped key.
        status,result=super().provision(uid,body)
        with self.store.connect() as db:db.execute("UPDATE relay_users SET status='pending' WHERE user_id=?",(uid,))
        with self.store.connect() as db:row=db.execute('SELECT * FROM relay_users WHERE user_id=?',(uid,)).fetchone()
        secret=self.unpack(row['secret']);grant=body['grantId']
        jwt=self.api('/api/v1/auth/login',{'email':secret['email'],'password':secret['password']})['access_token']
        groups=sorted(set(r['groupId'] for r in routes))
        self.api('/api/v1/admin/users/'+str(secret['sub2Id']),{'allowed_groups':groups,'restrict_public_groups':True,'concurrency':1,'rpm_limit':5},'PUT')
        if secret.get('routesGrant')!=grant:
            for key in secret.get('routeKeys',{}).values():
                if key['id']!=secret['keyId']:self.api('/api/v1/keys/'+str(key['id']),{'status':'inactive'},'PUT',jwt)
            secret.update(routesGrant=grant,routeKeys={str(self.config['sub2apiGroupId']):{'id':secret['keyId'],'key':secret['key']}},pendingRoutes={});self.save_secret(uid,secret)
        for group in groups:
            tag=str(group)
            if tag in secret['routeKeys']:continue
            if tag not in secret['pendingRoutes']:
                secret['pendingRoutes'][tag]='sk-'+secrets.token_hex(24);self.save_secret(uid,secret)
            raw=secret['pendingRoutes'][tag];name='FlowTodo '+grant[:8]+' group '+tag
            found=self.api('/api/v1/keys?page=1&page_size=100&search=FlowTodo',jwt=jwt)
            matches=found.get('items',[]) if isinstance(found,dict) else found
            key=next((k for k in matches if k.get('name')==name),None)
            key=key or self.api('/api/v1/keys',{'name':name,'custom_key':raw,'group_id':group,'quota':body['budgetUsd'],'expires_in_days':body['days'],'rate_limit_1d':body['budgetUsd'],'rate_limit_5h':body['budgetUsd'],'rate_limit_7d':body['budgetUsd']},jwt=jwt,idempotency=str(UUIDType(bytes=hashlib.sha256((grant+tag).encode()).digest()[:16])))
            secret['routeKeys'][tag]={'id':key['id'],'key':raw};self.save_secret(uid,secret)
        with self.store.connect() as db:db.execute("UPDATE relay_users SET status='active' WHERE user_id=?",(uid,))
        return status,result

    def ledger(self):
        with self.store.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS ai_spend(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,grant_id TEXT NOT NULL,amount REAL NOT NULL,status TEXT NOT NULL,created REAL NOT NULL)')

    def reserve(self,uid,grant,id,amount,budget):
        self.ledger()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM ai_spend WHERE id=?',(id,)).fetchone():raise Error(409,'该 AI 请求已经处理，请勿重复提交。')
            used=db.execute('SELECT coalesce(sum(amount),0) FROM ai_spend WHERE user_id=? AND grant_id=?',(uid,grant)).fetchone()[0]
            if used+amount>budget:raise Error(403,'本期官方 AI 金额额度不足，请减少输出长度或联系管理员。')
            db.execute("INSERT INTO ai_spend VALUES(?,?,?,?, 'held',?)",(id,uid,grant,amount,time.time()))

    def debit(self,id,status,amount=None):
        with self.store.connect() as db:
            if amount is None:db.execute('UPDATE ai_spend SET status=? WHERE id=?',(status,id))
            else:db.execute('UPDATE ai_spend SET status=?,amount=? WHERE id=?',(status,amount,id))

    def choose_routes(self,secret):
        routes=[r for r in self.routes() if str(r['groupId']) in secret.get('routeKeys',{})]
        if not routes:raise Error(503,'官方轮换密钥尚未配置完成。')
        offset=int(secret.get('rotation',0))%len(routes)
        return routes[offset:]+routes[:offset]

    def ceiling(self,route,encoded,limit):
        if not route.get('pricingVerified'):raise Error(503,'该官方模型价格上限尚未核验。')
        actual_input,actual_output=price_bounds(self.api,route['groupId'],route['model'])
        if actual_input>route['maxInputUsdPerMillion'] or actual_output>route['maxOutputUsdPerMillion']:raise Error(503,'模型计价发生变化，官方通道暂停该模型以保护金额额度。')
        return (encoded*route['maxInputUsdPerMillion']+limit*route['maxOutputUsdPerMillion'])/1_000_000

    def upstream(self,key,route,clean,limit,temperature):
        request=urllib.request.Request('http://127.0.0.1:18080/v1/chat/completions',data=dumps({'model':route['model'],'messages':clean,'max_tokens':limit,'stream':False,'temperature':temperature}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key},method='POST')
        with urllib.request.urlopen(request,timeout=75) as response:return json.loads(response.read(2_000_001))

    def chat(self,uid,body):
        with self.store.connect() as db:row=db.execute('SELECT * FROM relay_users WHERE user_id=?',(uid,)).fetchone()
        if not row or row['status']!='active' or row['expires']<time.time():raise Error(403,'官方额度尚未开通或已到期。')
        if not self.config.get('pricingVerified'):raise Error(503,'官方模型价格上限尚未核验。')
        messages=body.get('messages');limit=body.get('maxTokens');request_id=body.get('requestId')
        try:UUIDType(str(request_id))
        except ValueError:raise Error(400,'请求标识无效。')
        if not isinstance(messages,list) or not 1<=len(messages)<=40 or not isinstance(limit,int) or not 1<=limit<=8192:raise Error(400,'对话长度无效。')
        clean=[]
        for item in messages:
            if not isinstance(item,dict) or item.get('role') not in ('system','user','assistant') or not isinstance(item.get('content'),str):raise Error(400,'对话格式无效。')
            clean.append({'role':item['role'],'content':item['content']})
        encoded=len(dumps(clean).encode())
        if encoded>80000:raise Error(413,'对话过长，请减少背景。')
        secret=self.unpack(row['secret']);routes=self.choose_routes(secret)
        temperature=float(body.get('temperature',0.7))
        if not math.isfinite(temperature):raise Error(400,'参数无效。')
        secret['rotation']=int(secret.get('rotation',0))+1;self.save_secret(uid,secret)
        attempts=0
        for route in routes:
            try:amount=self.ceiling(route,encoded,limit)
            except Error as error:
                if error.status in (502,503):continue
                raise
            id=uid+':'+str(request_id)+':'+str(attempts)
            self.reserve(uid,row['grant_id'],id,amount,row['budget']);attempts+=1
            key=secret['routeKeys'][str(route['groupId'])]['key']
            try:
                data=self.upstream(key,route,clean,limit,min(1,max(0,temperature)))
                choice=data['choices'][0];content=choice['message']['content']
                if not isinstance(content,str) or not content.strip():raise ValueError('invalid_response')
                for value in secret['routeKeys'].values():content=content.replace(value['key'],'[已隐藏]')
                usage=data.get('usage') or {};safe={k:v for k,v in usage.items() if k in ('total_tokens','prompt_tokens','completion_tokens') and isinstance(v,int) and v>=0}
                # Charge a conservative ceiling to this private ledger; upstream billing may be lower.
                self.debit(id,'complete')
                return 200,{'choices':[{'message':{'role':'assistant','content':content},'finish_reason':choice.get('finish_reason','stop')}],'usage':safe}
            except urllib.error.HTTPError as error:
                # Preserve the ceiling even on definitive failures, preventing retry storms from overspending.
                self.debit(id,'failed_reserved')
                if error.code in (401,403,404,429,500,502,503) and attempts<len(routes):continue
                raise Error(503,'官方通道暂时不可用，本次调用次数未扣除。') from None
            except Exception:
                self.debit(id,'uncertain')
                raise Error(503,'官方请求结果无法确认，金额已预留；不会自动重试，请稍后联系管理员。') from None
        raise Error(503,'轮换通道暂时都不可用，请稍后重试。')
