"""Verify CF request-bound tickets locally; upstream credentials stay in the relay vault."""
import base64,hashlib,json,math,re,threading,time
from pathlib import Path
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding
from official_routing import OfficialRelay
from server_storage import Error

def decode(s):
    if not isinstance(s,str) or not re.fullmatch('[A-Za-z0-9_-]+',s):raise ValueError()
    return base64.urlsafe_b64decode(s+'='*((-len(s))%4))
def encode(s):return base64.urlsafe_b64encode(s).decode().rstrip('=')
class DirectAI:
    def __init__(self,config,store):
        self.config,self.store=config,store
        self.public=serialization.load_pem_public_key(config['aiTicketPublic'].encode())
        self.signer=serialization.load_pem_private_key(Path(config['aiReceiptPrivatePath']).read_bytes(),password=None)
        self.relay=OfficialRelay(config,store);self.guard=threading.Lock();self.busy=set()
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS direct_ai_requests(user_id TEXT,grant_id TEXT,request_id TEXT,payload_hash TEXT,status TEXT,response TEXT,created REAL,PRIMARY KEY(user_id,request_id))')
    def verify(self,ticket,payload):
        stage='format'
        try:
            if not isinstance(ticket,str) or len(ticket)>4096 or not isinstance(payload,str) or len(payload.encode())>100000:raise ValueError()
            h,p,s=ticket.split('.')
            if json.loads(decode(h))!={'alg':'RS256','typ':'JWT'}:raise ValueError()
            stage='signature';self.public.verify(decode(s),(h+'.'+p).encode(),padding.PKCS1v15(),hashes.SHA256())
            c=json.loads(decode(p));now=time.time()
            stage='issuer-time'
            if c['iss']!='https://app.cheemsdoge.xyz' or c['aud']!='flowtodo-xiangyang' or c['purpose']!='ai-call' or not now<c['exp']<=c['iat']+120 or not now-120<=c['iat']<=now+60:raise ValueError()
            stage='subject'
            for key in ('sub','grant','requestId'):
                if not re.fullmatch('[a-f0-9-]{36}',c[key]):raise ValueError()
            stage='quota'
            if c['plan'] not in ('free','lite','standard') or c['limit']!={'free':5,'lite':100,'standard':300}[c['plan']] or c['budgetUsd']!={'free':.02,'lite':.2,'standard':.4}[c['plan']] or c['grantExpires']<=now*1000:raise ValueError()
            stage='body-hash'
            if hashlib.sha256(payload.encode()).hexdigest()!=c['payloadHash']:raise ValueError()
            b=json.loads(payload)
            if b.get('requestId')!=c['requestId']:raise ValueError()
            return c,b
        except Exception as error:
            print('DIRECT_AI_PROOF_ERROR',stage,type(error).__name__,flush=True)
            raise Error(401,'官方调用凭证无效或过期，请重新发起。') from None
    def receipt(self,c,used):
        now=int(time.time());claims={'iss':'flowtodo-xiangyang','aud':'https://app.cheemsdoge.xyz','purpose':'ai-receipt','sub':c['sub'],'grant':c['grant'],'used':used,'iat':now,'exp':now+600}
        message=encode(b'{"alg":"RS256","typ":"JWT"}')+'.'+encode(json.dumps(claims,separators=(',',':')).encode())
        return message+'.'+encode(self.signer.sign(message.encode(),padding.PKCS1v15(),hashes.SHA256()))
    def handle(self,body):
        c,b=self.verify(body.get('ticket'),body.get('payload'));uid=c['sub']
        with self.guard:
            if uid in self.busy:raise Error(429,'官方通道正在处理上一条请求。')
            self.busy.add(uid)
        try:
            with self.store.connect() as db:
                prior=db.execute('SELECT * FROM direct_ai_requests WHERE user_id=? AND request_id=?',(uid,c['requestId'])).fetchone()
                used=db.execute("SELECT count(*) FROM direct_ai_requests WHERE user_id=? AND grant_id=? AND status IN ('complete','pending','uncertain')",(uid,c['grant'])).fetchone()[0]
            if prior:
                if prior['payload_hash']!=c['payloadHash'] or prior['grant_id']!=c['grant']:raise Error(409,'请求标识已使用。')
                if prior['status']=='complete':return 200,{**json.loads(prior['response']),'receipt':self.receipt(c,used)}
                raise Error(409,'该请求已经处理，请勿重复提交。')
            if used>=c['limit']:raise Error(403,'本期官方 AI 次数已经用完。')
            with self.store.connect() as db:
                recent=db.execute('SELECT count(*) FROM direct_ai_requests WHERE user_id=? AND created>?',(uid,time.time()-60)).fetchone()[0]
            if recent>=5:raise Error(429,'请求过于频繁，请稍后重试。')
            days=max(1,min(366,math.ceil((c['grantExpires']/1000-time.time())/86400)))
            self.relay.handle(uid,'/api/ai/provision',{'grantId':c['grant'],'budgetUsd':c['budgetUsd'],'days':days})
            with self.store.connect() as db:db.execute("INSERT INTO direct_ai_requests VALUES(?,?,?,?,'pending',NULL,?)",(uid,c['grant'],c['requestId'],c['payloadHash'],time.time()))
            try:status,result=self.relay.handle(uid,'/api/ai/chat',b)
            except Error as error:
                definitive=error.status in (400,403,413,422)
                with self.store.connect() as db:db.execute('UPDATE direct_ai_requests SET status=? WHERE user_id=? AND request_id=?',('failed' if definitive else 'uncertain',uid,c['requestId']))
                return error.status,{'error':error.message,'receipt':self.receipt(c,used+(0 if definitive else 1))}
            with self.store.connect() as db:db.execute("UPDATE direct_ai_requests SET status='complete',response=? WHERE user_id=? AND request_id=?",(json.dumps(result),uid,c['requestId']))
            return status,{**result,'receipt':self.receipt(c,used+1)}
        finally:
            with self.guard:self.busy.discard(uid)
