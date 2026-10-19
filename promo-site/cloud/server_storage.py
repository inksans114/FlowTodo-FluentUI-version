"""Isolated Xiangyang record store; all RPC traffic uses authenticated encryption."""
from __future__ import annotations
import base64
import json
import os
import re
import secrets
import sqlite3
import struct
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KINDS = ('tasks','flows','aiPlans')
LIMITS = {'free':(30,5,5,100*1048576),'lite':(300,50,50,1024*1048576),'standard':(2000,300,300,5*1024**3)}
UUID = re.compile(r'^[a-f0-9-]{36}$')
def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def dumps(value): return json.dumps(value,ensure_ascii=False,separators=(',',':'))
class Error(Exception):
    def __init__(self,status,message): self.status,self.message=status,message

class Connection(sqlite3.Connection):
    def __exit__(self,*args):
        try:return super().__exit__(*args)
        finally:self.close()

def avatar_valid(data):
    if data=='': return True
    if not isinstance(data,str) or len(data)>175000 or not data.startswith('data:image/png;base64,'): return False
    try:
        raw=base64.b64decode(data.split(',')[1],validate=True)
        return 33<=len(raw)<=131072 and raw[:8]==b'\x89PNG\r\n\x1a\n' and raw[12:16]==b'IHDR' and struct.unpack('>II',raw[16:24])==(256,256)
    except (ValueError,struct.error): return False

class Store:
    def __init__(self,path):
        self.path=str(path)
        with self.connect() as db:
            db.executescript('''PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,kind TEXT NOT NULL,title TEXT NOT NULL,payload TEXT NOT NULL,bytes INTEGER NOT NULL,version INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL,deleted_at TEXT);
            CREATE INDEX IF NOT EXISTS records_owner ON records(user_id,kind,deleted_at,id);
            CREATE UNIQUE INDEX IF NOT EXISTS records_uid ON records(user_id,json_extract(payload,'$._syncUid')) WHERE json_extract(payload,'$._syncUid') IS NOT NULL;
            CREATE TABLE IF NOT EXISTS avatars(user_id TEXT PRIMARY KEY,data TEXT NOT NULL,revision INTEGER NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS nonces(id TEXT PRIMARY KEY,expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS relay_users(user_id TEXT PRIMARY KEY,secret TEXT NOT NULL,grant_id TEXT,budget REAL NOT NULL DEFAULT 0,expires REAL NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'pending');
            ''')
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10,factory=Connection);db.row_factory=sqlite3.Row;return db
    @staticmethod
    def item(row):
        return {'id':row['id'],'kind':row['kind'],'title':row['title'],'payload':json.loads(row['payload']),'version':row['version'],'updatedAt':row['updated_at'],'deletedAt':row['deleted_at']}
    def quota(self,db,uid,plan,kind,size,exclude=''):
        limits=LIMITS.get(plan,LIMITS['free'])
        count=db.execute('SELECT count(*) FROM records WHERE user_id=? AND kind=? AND deleted_at IS NULL AND id<>?',(uid,kind,exclude)).fetchone()[0]
        total=db.execute('SELECT coalesce(sum(bytes),0) FROM records WHERE user_id=? AND id<>?',(uid,exclude)).fetchone()[0]
        if count>=limits[KINDS.index(kind)] or total+size>limits[3]:raise Error(409,'已达到当前会员的云端额度，请先整理记录。')
        # Tombstones are capped too, so deleting records cannot bypass the resource budget.
        all_count=db.execute('SELECT count(*) FROM records WHERE user_id=? AND id<>?',(uid,exclude)).fetchone()[0]
        if all_count>=sum(limits[:3])*2:raise Error(409,'回收站记录较多，请稍后重试或联系管理员。')
        global_size=db.execute('SELECT coalesce(sum(bytes),0) FROM records').fetchone()[0]
        if global_size+size>1024**3:raise Error(503,'云端空间暂时不足，本地数据仍然保留。')
    def handle(self,uid,plan,path,method,body):
        if not UUID.fullmatch(uid): raise Error(400,'账户标识无效。')
        from urllib.parse import urlsplit,parse_qs
        url=urlsplit(path);query=parse_qs(url.query)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("DELETE FROM records WHERE deleted_at IS NOT NULL AND deleted_at<?",(datetime.fromtimestamp(time.time()-7*86400,timezone.utc).isoformat().replace('+00:00','Z'),))
            if url.path=='/api/cloud/summary':
                usage={'tasks':0,'flows':0,'aiPlans':0,'aiCalls':0,'storageMB':0}
                for row in db.execute('SELECT kind,count(*) n FROM records WHERE user_id=? AND deleted_at IS NULL GROUP BY kind',(uid,)):
                    usage[row['kind']]=row['n']
                size=db.execute('SELECT coalesce(sum(bytes),0) FROM records WHERE user_id=?',(uid,)).fetchone()[0]
                avatar_size=db.execute('SELECT coalesce(length(data),0) FROM avatars WHERE user_id=?',(uid,)).fetchone()
                size+=avatar_size[0] if avatar_size else 0
                usage['storageMB']=round(size/1048576,2)
                rows=db.execute('SELECT * FROM records WHERE user_id=? AND deleted_at IS NULL ORDER BY updated_at DESC LIMIT 5',(uid,)).fetchall()
                avatar=db.execute('SELECT data,revision FROM avatars WHERE user_id=?',(uid,)).fetchone()
                return 200,{'usage':usage,'cloud':{'connected':True,'items':[self.item(r) for r in rows]},'avatar':dict(avatar) if avatar else {'data':'','revision':0}}
            if url.path=='/api/account/avatar':
                prior=db.execute('SELECT * FROM avatars WHERE user_id=?',(uid,)).fetchone()
                revision=prior['revision'] if prior else 0
                if method=='GET':return 200,{'data':prior['data'] if prior else '', 'revision':revision}
                if method!='PUT':raise Error(405,'不支持该操作。')
                if not avatar_valid(body.get('data')):raise Error(400,'请选择 256×256 PNG 头像，最多 128 KB。')
                if body.get('revision')!=revision:raise Error(409,'头像已在另一端修改，请刷新后重试。')
                if db.execute('PRAGMA page_count').fetchone()[0]*db.execute('PRAGMA page_size').fetchone()[0]>1024**3:raise Error(503,'云端空间暂时不足。')
                db.execute('INSERT INTO avatars VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data,revision=excluded.revision,updated_at=excluded.updated_at',(uid,body['data'],revision+1,now()))
                return 200,{'revision':revision+1,'data':body['data']}
            if url.path=='/api/cloud/items' and method=='GET':
                kind=query.get('kind',[''])[0];trash=query.get('trash',['0'])[0]=='1';after=query.get('after',[''])[0]
                if kind and kind not in KINDS:raise Error(400,'未知数据类型。')
                rows=db.execute(f"SELECT * FROM records WHERE user_id=? AND deleted_at IS {'NOT ' if trash else ''}NULL AND (?='' OR kind=?) AND id>? ORDER BY id LIMIT 26",(uid,kind,kind,after)).fetchall()
                return 200,{'items':[self.item(r) for r in rows[:25]],'next':rows[24]['id'] if len(rows)>25 else None}
            if url.path=='/api/cloud/export' and method=='GET':
                return 200,{'format':'flowtodo-cloud-v1','exportedAt':now(),'items':[self.item(r) for r in db.execute('SELECT * FROM records WHERE user_id=? ORDER BY updated_at DESC',(uid,))]}
            if url.path=='/api/cloud/items' and method=='POST':
                kind=body.get('kind');title=str(body.get('title') or '').strip();payload=body.get('payload')
                if kind not in KINDS or not title or len(title)>120 or not isinstance(payload,dict):raise Error(400,'记录类型、标题或内容不正确。')
                text=dumps(payload);size=len((text+title).encode())
                if size>16384:raise Error(413,'单条记录最多 16 KB，请分批保存。')
                key=payload.get('_syncUid')
                if key:
                    if not isinstance(key,str) or len(key)>80:raise Error(400,'同步标识无效。')
                    existing=db.execute("SELECT * FROM records WHERE user_id=? AND json_extract(payload,'$._syncUid')=?",(uid,key)).fetchone()
                    if existing:return 201,{'item':self.item(existing)}
                self.quota(db,uid,plan,kind,size)
                id=str(uuid4());db.execute('INSERT INTO records(id,user_id,kind,title,payload,bytes,updated_at) VALUES(?,?,?,?,?,?,?)',(id,uid,kind,title,text,size,now()))
                return 201,{'item':self.item(db.execute('SELECT * FROM records WHERE id=?',(id,)).fetchone())}
            match=re.fullmatch(r'/api/cloud/items/([a-f0-9-]{36})(/restore)?',url.path)
            if match and method in ('PATCH','DELETE','POST'):
                row=db.execute('SELECT * FROM records WHERE id=? AND user_id=?',(match[1],uid)).fetchone()
                if not row:raise Error(404,'记录不存在。')
                if body.get('version')!=row['version']:raise Error(409,'记录已修改，请刷新后重试。')
                title,payload,deleted=row['title'],row['payload'],row['deleted_at']
                if method=='DELETE' and not match[2]:deleted=now()
                elif method=='POST' and match[2] and deleted:deleted=None
                elif method=='PATCH' and not match[2] and not deleted:
                    title=str(body.get('title') or '').strip()
                    if not title or len(title)>120 or not isinstance(body.get('payload'),dict):raise Error(400,'标题或内容无效。')
                    payload=dumps(body['payload'])
                else:raise Error(400,'该操作不适用于当前记录。')
                size=len((title+payload).encode())
                if size>16384:raise Error(413,'单条记录最多 16 KB。')
                if not deleted:self.quota(db,uid,plan,row['kind'],size,row['id'])
                db.execute('UPDATE records SET title=?,payload=?,bytes=?,version=version+1,updated_at=?,deleted_at=? WHERE id=?',(title,payload,size,now(),deleted,row['id']))
                return 200,{'ok':True}
            raise Error(404,'未找到此功能。')

class RPC:
    def __init__(self,config):
        self.config=config;self.aes=AESGCM(bytes.fromhex(config['storageKey']));self.store=Store(config['database']);self.slots=threading.BoundedSemaphore(8)
    def execute(self,envelope):
        raw=self.aes.decrypt(base64.b64decode(envelope['nonce'],validate=True),base64.b64decode(envelope['data'],validate=True),b'flowtodo-storage-request-v1')
        request=json.loads(raw)
        if not UUID.fullmatch(request['id']) or abs(time.time()*1000-request['at'])>60000:raise ValueError('expired')
        with self.store.connect() as db:
            db.execute('DELETE FROM nonces WHERE expires<?',(time.time(),))
            db.execute('INSERT INTO nonces VALUES(?,?)',(request['id'],time.time()+120))
        try:
            if request['path']=='/api/cloud/admin-summary':
                if request['user'].get('role')!='admin':raise Error(403,'需要管理员权限。')
                with self.store.connect() as db:
                    stats=db.execute('SELECT count(*) AS records,coalesce(sum(bytes),0) AS bytes FROM records WHERE deleted_at IS NULL').fetchone()
                    status,data=200,dict(stats)
            elif request['path'].startswith('/api/ai/'):
                if request['path']=='/api/ai/provision' and request['user'].get('role')!='admin':raise Error(403,'需要管理员权限。')
                from official_routing import OfficialRelay
                status,data=OfficialRelay(self.config,self.store).handle(request['user']['id'],request['path'],request['body'])
            else:status,data=self.store.handle(request['user']['id'],request['user']['plan'],request['path'],request['method'],request['body'])
        except Error as error:status,data=error.status,{'error':error.message}
        except Exception:status,data=503,{'error':'后端暂时不可用，请稍后重试。'}
        nonce=secrets.token_bytes(12)
        data=self.aes.encrypt(nonce,dumps({'id':request['id'],'at':int(time.time()*1000),'status':status,'data':data}).encode(),b'flowtodo-storage-response-v1')
        return {'nonce':base64.b64encode(nonce).decode(),'data':base64.b64encode(data).decode()}

def serve(config):
    rpc=RPC(config)
    direct=None
    if config.get('aiTicketPublic'):
        from ai_direct import DirectAI
        direct=DirectAI(config,rpc.store)
        from cloud_direct import DirectCloud
        direct_cloud=DirectCloud(config,rpc.store)
    identity=None
    if config.get('identityPublicKey'):
        from identity_api import IdentityAPI
        identity=IdentityAPI(config,rpc.store)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def identity_request(self):
            if not identity:self.send_error(503);return
            if not rpc.slots.acquire(blocking=False):self.send_error(503);return
            try:
                self.connection.settimeout(20);size=int(self.headers.get('Content-Length','0'))
                limit=180000 if self.path=='/api/account/avatar' else 100000 if self.path=='/api/ai/chat' else 32768
                if not 0<=size<=limit:raise Error(413,'请求过大。')
                if self.command not in ('GET','HEAD') and not self.headers.get('Content-Type','').startswith('application/json'):raise Error(400,'请求格式不正确。')
                raw=self.rfile.read(size)
                if self.path=='/api/payments/wechat/notify' and self.command=='POST':
                    status,data,extra=identity.payment_notification(self.headers,raw)
                else:
                    body=json.loads(raw) if size else {}
                    if not isinstance(body,dict):raise Error(400,'请求格式不正确。')
                    status,data,extra=identity.handle(self.path,self.command,body,self.headers)
            except Error as error:status,data,extra=error.status,{'error':error.message},{}
            except Exception:status,data,extra=503,{'error':'账户服务暂时不可用。'},{}
            finally:rpc.slots.release()
            output=dumps(data).encode();self.send_response(status)
            for k,v in {'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','Content-Length':str(len(output)),**extra}.items():self.send_header(k,v)
            self.end_headers();self.wfile.write(output)
        do_GET=identity_request
        do_PUT=identity_request
        do_PATCH=identity_request
        do_DELETE=identity_request
        def do_POST(self):
            if self.path in ('/api/ai/direct','/api/cloud/direct') and direct:
                if not rpc.slots.acquire(blocking=False):self.send_error(503);return
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=240000:raise Error(413,'请求过大。')
                    self.connection.settimeout(300)
                    status,result=(direct_cloud if self.path=='/api/cloud/direct' else direct).handle(json.loads(self.rfile.read(size)))
                except Error as error:status,result=error.status,{'error':error.message}
                except Exception as error:
                    if hasattr(error,'status') and hasattr(error,'message'):
                        status,result=error.status,{'error':error.message}
                    else:
                        import traceback
                        frames=[(Path(frame.filename).name,frame.name,frame.lineno) for frame in traceback.extract_tb(error.__traceback__)]
                        print('DIRECT_AI_ERROR',type(error).__name__,frames,flush=True)
                        status,result=503,{'error':'官方直连暂时不可用。'}
                finally:rpc.slots.release()
                output=dumps(result).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(output)));self.end_headers();self.wfile.write(output);return
            if self.path.startswith('/api/'):
                self.identity_request();return
            if self.path!='/rpc':self.send_error(404);return
            try:size=int(self.headers.get('Content-Length','0'))
            except ValueError:self.send_error(400);return
            if not 0<size<=300000:self.send_error(413);return
            if not rpc.slots.acquire(blocking=False):self.send_error(503);return
            try:
                self.connection.settimeout(20)
                output=dumps(rpc.execute(json.loads(self.rfile.read(size)))).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(output)));self.end_headers();self.wfile.write(output)
            except Exception:self.send_error(403)
            finally:rpc.slots.release()
    ThreadingHTTPServer(('127.0.0.1',4191),Handler).serve_forever()

if __name__=='__main__':
    serve(json.loads(Path(os.environ.get('FLOWTODO_CLOUD_CONFIG','/etc/flowtodo-cloud/credentials.json')).read_text()))
