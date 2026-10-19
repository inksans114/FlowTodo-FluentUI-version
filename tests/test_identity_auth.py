import base64
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from uuid import uuid4
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import rsa,padding
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'promo-site/cloud'))
from identity_auth import IdentityAuth
from identity_api import IdentityAPI
from server_storage import Store,Error

def enc(data):return base64.urlsafe_b64encode(data).decode().rstrip('=')

class IdentityTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'db.sqlite')
  self.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  self.config={'identityIssuer':'https://app.cheemsdoge.xyz','identityOrigin':'https://dashboard.cheemsdoge.xyz:24336','identityKeyId':'test','identityPublicKey':self.key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()}
  self.auth=IdentityAuth(self.config,self.store);self.api=IdentityAPI(self.config,self.store)
  self.headers={'Origin':self.config['identityOrigin'],'X-FlowTodo-Request':'1'}
  _,start,cookies=self.api.handle('/api/identity/start','POST',{},self.headers)
  self.state=start['state'];self.headers['Cookie']=cookies['Set-Cookie'].split(';')[0]
 def tearDown(self):self.temp.cleanup()
 def ticket(self,**extra):
  now=int(time.time());c={'iss':self.config['identityIssuer'],'aud':self.config['identityOrigin'],'purpose':'mailbox-login','email':'a@example.com','name':'A','state':self.state,'iat':now,'exp':now+120,'jti':str(uuid4()),**extra}
  h=enc(json.dumps({'alg':'RS256','typ':'JWT','kid':'test'}).encode());p=enc(json.dumps(c).encode());msg=h+'.'+p
  return msg+'.'+enc(self.key.sign(msg.encode(),padding.PKCS1v15(),hashes.SHA256()))
 def test_single_use_and_server_owns_permissions(self):
  token=self.ticket(plan='standard',role='admin',balance=10000)
  raw,csrf,user=self.auth.exchange(token)
  self.assertEqual((user['plan'],user['role'],user['balance_cents']),('free','user',0))
  self.assertEqual(self.auth.session(raw)['id'],user['id'])
  with self.assertRaises(Error):self.auth.exchange(token)
 def test_reject_tampered_expired_wrong_audience(self):
  for token in (self.ticket(exp=int(time.time())-1),self.ticket(aud='https://evil.example'),self.ticket().rsplit('.',1)[0]+'.AAAA'):
   with self.assertRaises(Error):self.auth.exchange(token)
 def test_existing_account_keeps_server_plan_and_name(self):
  _,_,user=self.auth.exchange(self.ticket())
  with self.store.connect() as db:db.execute("UPDATE accounts SET plan='lite',name='Local account' WHERE id=?",(user['id'],))
  _,_,again=self.auth.exchange(self.ticket(name='Override'))
  self.assertEqual((again['id'],again['plan'],again['name']),(user['id'],'lite','Local account'))
 def test_device_approval_revocation_and_storage(self):
  _,result,cookies=self.api.handle('/api/identity/exchange','POST',{'ticket':self.ticket()},self.headers)
  browser={**self.headers,'Cookie':cookies['Set-Cookie'].split(';')[0],'X-CSRF-Token':result['csrf']}
  _,start,_=self.api.handle('/api/device/start','POST',{'name':'Test'},self.headers)
  self.assertEqual(self.api.handle('/api/device/poll','POST',{'deviceCode':start['deviceCode']},self.headers)[0],202)
  self.api.handle('/api/device/authorize','POST',{'userCode':start['userCode'],'confirm':True},browser)
  _,session,_=self.api.handle('/api/device/poll','POST',{'deviceCode':start['deviceCode']},self.headers)
  native={**self.headers,'Authorization':'Bearer '+session['accessToken']}
  _,item,_=self.api.handle('/api/cloud/items','POST',{'kind':'tasks','title':'Native','payload':{}},native)
  self.assertEqual(self.api.handle('/api/cloud/items','GET',{},browser)[1]['items'][0]['id'],item['item']['id'])
  with self.assertRaises(Error):self.api.handle('/api/admin/overview','GET',{},native)
  self.api.handle('/api/account/device','DELETE',{'id':session['deviceId']},browser)
  with self.assertRaises(Error):self.api.handle('/api/account','GET',{},native)
 def test_csrf_and_origin(self):
  _,result,cookies=self.api.handle('/api/identity/exchange','POST',{'ticket':self.ticket()},self.headers)
  with self.assertRaises(Error):self.api.handle('/api/account/profile','PATCH',{'name':'Bad'},{**self.headers,'Cookie':cookies['Set-Cookie'].split(';')[0]})
  with self.assertRaises(Error):self.api.handle('/api/identity/exchange','POST',{'ticket':self.ticket()},{'Origin':'http://attacker.example','X-FlowTodo-Request':'1'})
 def test_native_code_bound_to_device_and_attempt_limit(self):
  self.auth.exchange(self.ticket())
  self.config.update(storageKey='test-secret',smtpUser='sender@example.com',smtpPassword='test')
  sent=[];self.api.native.sender=lambda email,code:sent.append(code)
  _,start,_=self.api.handle('/api/device/start','POST',{},self.headers)
  body={'deviceCode':start['deviceCode'],'email':'a@example.com'}
  self.api.handle('/api/native/send-code','POST',body,self.headers)
  for _ in range(5):
   with self.assertRaises(Error):self.api.handle('/api/native/verify','POST',{**body,'code':'bad'},self.headers)
  with self.assertRaises(Error):self.api.handle('/api/native/verify','POST',{**body,'code':sent[0]},self.headers)
  _,other,_=self.api.handle('/api/device/start','POST',{},self.headers)
  with self.assertRaises(Error):self.api.handle('/api/native/verify','POST',{**body,'deviceCode':other['deviceCode'],'code':sent[0]},self.headers)
 def test_native_login_single_use_and_revoke(self):
  self.auth.exchange(self.ticket())
  self.config.update(storageKey='test-secret',smtpUser='sender@example.com',smtpPassword='test')
  sent=[];self.api.native.sender=lambda email,code:sent.append(code)
  _,start,_=self.api.handle('/api/device/start','POST',{},self.headers)
  body={'deviceCode':start['deviceCode'],'email':'a@example.com'}
  self.api.handle('/api/native/send-code','POST',body,self.headers)
  _,result,_=self.api.handle('/api/native/verify','POST',{**body,'code':sent[0]},self.headers)
  with self.assertRaises(Error):self.api.handle('/api/native/verify','POST',{**body,'code':sent[0]},self.headers)
  headers={**self.headers,'Authorization':'Bearer '+result['accessToken']}
  self.assertEqual(self.api.handle('/api/account','GET',{},headers)[1]['user']['email'],'a@example.com')
  self.api.handle('/api/auth/logout','POST',{},headers)
  with self.assertRaises(Error):self.api.handle('/api/account','GET',{},headers)

if __name__=='__main__':unittest.main()
