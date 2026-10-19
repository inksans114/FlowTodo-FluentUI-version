"""Xiangyang owns accounts. Mailbox tickets prove identity, never membership."""
import base64
import hashlib
import json
import re
import secrets
import time
from uuid import uuid4
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from server_storage import Error

def decode(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', value): raise ValueError('encoding')
    return base64.urlsafe_b64decode(value+'='*((-len(value))%4))

class IdentityAuth:
    def __init__(self,config,store):
        self.config,self.store=config,store
        self.key=serialization.load_pem_public_key(config['identityPublicKey'].encode())
        if not isinstance(self.key,rsa.RSAPublicKey) or self.key.key_size<2048: raise ValueError('Invalid verification key')
        with store.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,plan TEXT NOT NULL DEFAULT 'free',role TEXT NOT NULL DEFAULT 'user',balance_cents INTEGER NOT NULL DEFAULT 0,created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS login_tickets(jti TEXT PRIMARY KEY,expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS account_sessions(hash TEXT PRIMARY KEY,user_id TEXT NOT NULL,csrf TEXT NOT NULL,expires REAL NOT NULL);
            ''')

    def verify(self,ticket):
        try:
            if not isinstance(ticket,str) or len(ticket)>4096: raise ValueError('size')
            header,payload,signature=ticket.split('.')
            h=json.loads(decode(header));c=json.loads(decode(payload))
            if h!={'alg':'RS256','typ':'JWT','kid':self.config['identityKeyId']}:raise ValueError('header')
            self.key.verify(decode(signature),(header+'.'+payload).encode(),padding.PKCS1v15(),hashes.SHA256())
            now=time.time()
            if c.get('iss')!=self.config['identityIssuer'] or c.get('aud')!=self.config['identityOrigin'] or c.get('purpose')!='mailbox-login':raise ValueError('audience')
            if not isinstance(c.get('iat'),int) or not isinstance(c.get('exp'),int) or not now-120<=c['iat']<=now+5 or not now<c['exp']<=c['iat']+120:raise ValueError('expiry')
            if not re.fullmatch(r'[a-f0-9-]{36}',c.get('jti','')):raise ValueError('id')
            email=c.get('email','')
            if not isinstance(email,str) or len(email)>254 or not re.fullmatch(r'[a-zA-Z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',email):raise ValueError('email')
            name=c.get('name','')
            if not isinstance(name,str) or len(name)>40:raise ValueError('name')
            return c
        except Exception:raise Error(401,'登录凭证无效或已过期，请重新登录。') from None

    def exchange(self,ticket):
        c=self.verify(ticket);now=time.time();email=c['email'].lower()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM login_tickets WHERE expires<?',(now-300,))
            try:db.execute('INSERT INTO login_tickets VALUES(?,?)',(c['jti'],c['exp']))
            except Exception:raise Error(401,'登录凭证已使用，请重新登录。') from None
            row=db.execute('SELECT * FROM accounts WHERE email=?',(email,)).fetchone()
            if not row:
                # No plan/role/balance claims are accepted from the ticket or browser.
                db.execute('INSERT INTO accounts(id,email,name,created_at) VALUES(?,?,?,?)',(str(uuid4()),email,c['name'] or email.split('@')[0][:40],now))
                row=db.execute('SELECT * FROM accounts WHERE email=?',(email,)).fetchone()
            raw,csrf=secrets.token_hex(32),secrets.token_hex(32)
            db.execute('DELETE FROM account_sessions WHERE expires<?',(now,))
            db.execute('INSERT INTO account_sessions VALUES(?,?,?,?)',(hashlib.sha256(raw.encode()).hexdigest(),row['id'],csrf,now+7*86400))
            result={k:row[k] for k in ('id','email','name','plan','role','balance_cents','created_at')}
        return raw,csrf,result

    def session(self,raw):
        if not re.fullmatch(r'[a-f0-9]{64}',raw or ''):raise Error(401,'请先登录。')
        with self.store.connect() as db:
            row=db.execute('SELECT a.*,s.csrf,s.hash FROM account_sessions s JOIN accounts a ON a.id=s.user_id WHERE s.hash=? AND s.expires>?',(hashlib.sha256(raw.encode()).hexdigest(),time.time())).fetchone()
        if not row:raise Error(401,'登录已失效，请重新登录。')
        return dict(row)
