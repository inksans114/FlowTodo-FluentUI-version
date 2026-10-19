"""Order ledger and verified merchant receipts. A personal QR code is not an API."""
import base64,json,secrets,time
from uuid import uuid4
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from server_storage import Error

CATALOG={'lite':{'monthly':599,'annual':5990},'standard':{'monthly':999,'annual':9990}}

class WechatReceipt:
    def __init__(self,config):self.config=config
    def verify(self,headers,raw):
        try:
            timestamp=headers['Wechatpay-Timestamp'];nonce=headers['Wechatpay-Nonce']
            if abs(time.time()-int(timestamp))>300 or len(nonce)>128 or len(raw)>65536:raise ValueError()
            if headers['Wechatpay-Serial']!=self.config['wechatPublicKeyId']:raise ValueError()
            key=serialization.load_pem_public_key(self.config['wechatPublicKey'].encode())
            signed=timestamp.encode()+b'\n'+nonce.encode()+b'\n'+raw+b'\n'
            key.verify(base64.b64decode(headers['Wechatpay-Signature'],validate=True),signed,padding.PKCS1v15(),hashes.SHA256())
            envelope=json.loads(raw);resource=envelope['resource']
            if envelope['event_type']!='TRANSACTION.SUCCESS' or resource['algorithm']!='AEAD_AES_256_GCM':raise ValueError()
            clear=AESGCM(self.config['wechatApiV3Key'].encode()).decrypt(resource['nonce'].encode(),base64.b64decode(resource['ciphertext'],validate=True),resource.get('associated_data','').encode())
            receipt=json.loads(clear)
            if receipt['mchid']!=self.config['wechatMerchantId'] or receipt['appid']!=self.config['wechatAppId'] or receipt['trade_state']!='SUCCESS' or receipt['amount']['currency']!='CNY':raise ValueError()
            return receipt
        except Exception:raise Error(401,'支付通知验证失败。') from None

class Billing:
    def __init__(self,config,store):
        self.config,self.store=config,store
        with store.connect() as db:db.executescript('''
        CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,plan TEXT NOT NULL,cycle TEXT NOT NULL,amount_cents INTEGER NOT NULL,status TEXT NOT NULL,created REAL NOT NULL,expires REAL NOT NULL,paid REAL,transaction_id TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS subscriptions(user_id TEXT PRIMARY KEY,plan TEXT NOT NULL,expires REAL NOT NULL,order_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS payment_grants(order_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,plan TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending');
        ''')
    def create(self,user,body):
        plan,cycle=body.get('plan'),body.get('cycle')
        if plan not in CATALOG or cycle not in CATALOG[plan]:raise Error(400,'请选择有效会员方案。')
        if self.config.get('paymentMode')!='wechat':raise Error(503,'自动收款渠道尚未配置。个人收款码暂不支持自动核账。')
        id=uuid4().hex;now=time.time()
        with self.store.connect() as db:
            pending=db.execute("SELECT count(*) FROM orders WHERE user_id=? AND status='pending' AND expires>?",(user['id'],now)).fetchone()[0]
            if pending>=3:raise Error(429,'请先完成已有订单。')
            db.execute('INSERT INTO orders VALUES(?,?,?,?,?,\'pending\',?,?,NULL,NULL)',(id,user['id'],plan,cycle,CATALOG[plan][cycle],now,now+1800))
        return self.get(user['id'],id)
    def get(self,uid,id):
        with self.store.connect() as db:row=db.execute('SELECT * FROM orders WHERE user_id=? AND id=?',(uid,id)).fetchone()
        if not row:raise Error(404,'订单不存在。')
        return dict(row)
    def apply(self,receipt):
        # Called only with the verifier's server-side result, never a client status.
        amount=receipt.get('amount',{}).get('total');transaction=receipt.get('transaction_id')
        if type(amount) is not int or not isinstance(transaction,str) or not 1<=len(transaction)<=64:raise Error(400,'支付数据无效。')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            order=db.execute('SELECT * FROM orders WHERE id=?',(receipt.get('out_trade_no'),)).fetchone()
            if not order or order['amount_cents']!=amount:raise Error(409,'支付订单或金额不一致。')
            if order['status']=='paid':
                if order['transaction_id']!=transaction:raise Error(409,'交易号与已有支付不一致。')
                return {'paid':True,'duplicate':True}
            used=db.execute('SELECT id FROM orders WHERE transaction_id=?',(transaction,)).fetchone()
            if used:raise Error(409,'该交易已绑定其他订单。')
            now=time.time();days=365 if order['cycle']=='annual' else 31
            prior=db.execute('SELECT * FROM subscriptions WHERE user_id=?',(order['user_id'],)).fetchone()
            if prior and prior['expires']>now and prior['plan']!=order['plan']:raise Error(409,'跨方案付款需要人工处理，避免覆盖剩余会员。')
            expires=max(now,prior['expires'] if prior else 0)+days*86400
            db.execute("UPDATE orders SET status='paid',paid=?,transaction_id=? WHERE id=?",(now,transaction,order['id']))
            db.execute('INSERT INTO subscriptions VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET plan=excluded.plan,expires=excluded.expires,order_id=excluded.order_id',(order['user_id'],order['plan'],expires,order['id']))
            db.execute('UPDATE accounts SET plan=? WHERE id=?',(order['plan'],order['user_id']))
            db.execute('INSERT INTO payment_grants VALUES(?,?,?,\'pending\')',(order['id'],order['user_id'],order['plan']))
        return {'paid':True,'duplicate':False}
