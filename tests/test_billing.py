import base64,json,sys,tempfile,time,unittest
from pathlib import Path
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'promo-site/cloud'))
from server_storage import Store,Error
from identity_auth import IdentityAuth
from billing import Billing,WechatReceipt

class BillingTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'db')
  self.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  self.config={'identityPublicKey':self.key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode(),'paymentMode':'wechat','wechatMerchantId':'merchant','wechatAppId':'app','wechatPublicKeyId':'PUB_KEY_ID','wechatApiV3Key':'a'*32}
  self.config['wechatPublicKey']=self.config['identityPublicKey'];IdentityAuth(self.config,self.store)
  with self.store.connect() as db:db.execute("INSERT INTO accounts VALUES('u','u@example.com','U','free','user',0,?)",(time.time(),))
  self.billing=Billing(self.config,self.store);self.order=self.billing.create({'id':'u'},{'plan':'lite','cycle':'monthly','amount_cents':1})
 def tearDown(self):self.temp.cleanup()
 def receipt(self):return {'out_trade_no':self.order['id'],'transaction_id':'wx1','amount':{'total':599,'currency':'CNY'},'mchid':'merchant','appid':'app','trade_state':'SUCCESS'}
 def test_server_price_order_ownership_and_idempotency(self):
  self.assertEqual(self.order['amount_cents'],599)
  with self.assertRaises(Error):self.billing.get('other',self.order['id'])
  self.assertFalse(self.billing.apply(self.receipt())['duplicate']);self.assertTrue(self.billing.apply(self.receipt())['duplicate'])
  with self.store.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM payment_grants').fetchone()[0],1)
 def test_amount_mismatch_does_not_open_membership(self):
  r=self.receipt();r['amount']['total']=1
  with self.assertRaises(Error):self.billing.apply(r)
  with self.store.connect() as db:self.assertEqual(db.execute('SELECT plan FROM accounts').fetchone()[0],'free')
 def test_signed_encrypted_receipt_and_forgery_rejection(self):
  nonce='0123456789ab';aad='transaction';encrypted=AESGCM(b'a'*32).encrypt(nonce.encode(),json.dumps(self.receipt()).encode(),aad.encode())
  raw=json.dumps({'event_type':'TRANSACTION.SUCCESS','resource':{'algorithm':'AEAD_AES_256_GCM','nonce':nonce,'associated_data':aad,'ciphertext':base64.b64encode(encrypted).decode()}}).encode()
  stamp=str(int(time.time()));signed=stamp.encode()+b'\nnotify\n'+raw+b'\n'
  headers={'Wechatpay-Timestamp':stamp,'Wechatpay-Nonce':'notify','Wechatpay-Serial':'PUB_KEY_ID','Wechatpay-Signature':base64.b64encode(self.key.sign(signed,padding.PKCS1v15(),hashes.SHA256())).decode()}
  verifier=WechatReceipt(self.config);self.assertEqual(verifier.verify(headers,raw)['transaction_id'],'wx1')
  with self.assertRaises(Error):verifier.verify(headers,raw+b' ')
  with self.assertRaises(Error):verifier.verify({**headers,'Wechatpay-Serial':'attacker'},raw)

if __name__=='__main__':unittest.main()
