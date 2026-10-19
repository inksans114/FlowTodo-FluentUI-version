"""Desktop-only content transport. Cloudflare receives signed counters only."""
import hashlib,json,re,time,threading
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding
from pathlib import Path
from ai_direct import decode,encode
from server_storage import Error

class DirectCloud:
    def __init__(self,config,store):
        self.store=store;self.lock=threading.Lock()
        self.public=serialization.load_pem_public_key(config['aiTicketPublic'].encode())
        self.signer=serialization.load_pem_private_key(Path(config['aiReceiptPrivatePath']).read_bytes(),None)
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS cloud_usage_versions(user_id TEXT PRIMARY KEY,revision INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS cloud_direct_requests(user_id TEXT,request_id TEXT,hash TEXT,status INTEGER,response TEXT,created REAL,PRIMARY KEY(user_id,request_id))')
    def handle(self,body):
        try:
            payload=body['payload'];h,p,s=body['ticket'].split('.')
            if len(payload.encode())>190000 or json.loads(decode(h))!={'alg':'RS256','typ':'JWT'}:raise ValueError()
            self.public.verify(decode(s),(h+'.'+p).encode(),padding.PKCS1v15(),hashes.SHA256())
            c=json.loads(decode(p));now=time.time();b=json.loads(payload)
            if c['iss']!='https://app.cheemsdoge.xyz' or c['aud']!='flowtodo-xiangyang' or c['purpose']!='cloud-call' or not now<c['exp']<=c['iat']+120 or not now-120<=c['iat']<=now+60:raise ValueError()
            if c['plan'] not in ('free','lite','standard') or not re.fullmatch('[a-f0-9-]{36}',c['sub']) or not re.fullmatch('[a-f0-9-]{36}',c['requestId']):raise ValueError()
            if hashlib.sha256(payload.encode()).hexdigest()!=c['payloadHash'] or b['requestId']!=c['requestId']:raise ValueError()
            path=b['path'];method=b['method']
            if not re.fullmatch(r'/api/cloud/(summary|export|items(?:/[a-f0-9-]{36}(?:/restore)?)?)(?:\?[^#]*)?|/api/account/avatar',path) or method not in ('GET','POST','PATCH','PUT','DELETE'):raise ValueError()
        except Exception:raise Error(401,'存储凭证无效或已过期，请重新同步。') from None
        uid=c['sub']
        with self.lock:
            with self.store.connect() as db:
                db.execute('DELETE FROM cloud_direct_requests WHERE created<?',(now-86400,))
                prior=db.execute('SELECT * FROM cloud_direct_requests WHERE user_id=? AND request_id=?',(uid,c['requestId'])).fetchone()
            if prior:
                if prior['hash']!=c['payloadHash']:raise Error(409,'请求标识已使用。')
                status,result=prior['status'],json.loads(prior['response'])
            else:
                status,result=self.store.handle(uid,c['plan'],path,method,b.get('body') or {})
                if method!='GET':
                    with self.store.connect() as db:db.execute('INSERT INTO cloud_direct_requests VALUES(?,?,?,?,?,?)',(uid,c['requestId'],c['payloadHash'],status,json.dumps(result),now))
            with self.store.connect() as db:
                db.execute('INSERT INTO cloud_usage_versions VALUES(?,1) ON CONFLICT(user_id) DO UPDATE SET revision=revision+1',(uid,))
                revision=db.execute('SELECT revision FROM cloud_usage_versions WHERE user_id=?',(uid,)).fetchone()[0]
                counts={r['kind']:r['n'] for r in db.execute('SELECT kind,count(*) n FROM records WHERE user_id=? AND deleted_at IS NULL GROUP BY kind',(uid,))}
                size=db.execute('SELECT coalesce(sum(bytes),0) FROM records WHERE user_id=?',(uid,)).fetchone()[0]
                avatar=db.execute('SELECT data FROM avatars WHERE user_id=?',(uid,)).fetchone()
                if avatar:size+=len(avatar['data'].encode())
            claims={'iss':'flowtodo-xiangyang','aud':'https://app.cheemsdoge.xyz','purpose':'cloud-usage','sub':uid,'tasks':counts.get('tasks',0),'flows':counts.get('flows',0),'aiPlans':counts.get('aiPlans',0),'bytes':size,'revision':revision,'iat':int(now),'exp':int(now)+600}
            message=encode(b'{"alg":"RS256","typ":"JWT"}')+'.'+encode(json.dumps(claims,separators=(',',':')).encode())
            return status,{**result,'receipt':message+'.'+encode(self.signer.sign(message.encode(),padding.PKCS1v15(),hashes.SHA256()))}
