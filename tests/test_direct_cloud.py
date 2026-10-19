import sys,tempfile,json,time,hashlib,unittest
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'promo-site/cloud'))
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.hazmat.primitives import serialization,hashes
from cloud_direct import DirectCloud
from ai_direct import encode,decode
from server_storage import Store,Error
class DirectStorageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();p=Path(self.tmp.name);self.auth=rsa.generate_private_key(public_exponent=65537,key_size=2048);receipt=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  (p/'key').write_bytes(receipt.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
  self.store=Store(p/'db');self.gateway=DirectCloud({'aiTicketPublic':self.auth.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode(),'aiReceiptPrivatePath':str(p/'key')},self.store);self.uid=str(uuid4())
 def tearDown(self):self.tmp.cleanup()
 def request(self,path,method='GET',body=None,uid=None):
  b={'requestId':str(uuid4()),'path':path,'method':method,'body':body};payload=json.dumps(b,separators=(',',':'));now=int(time.time())
  c={'iss':'https://app.cheemsdoge.xyz','aud':'flowtodo-xiangyang','purpose':'cloud-call','sub':uid or self.uid,'plan':'free','requestId':b['requestId'],'payloadHash':hashlib.sha256(payload.encode()).hexdigest(),'iat':now,'exp':now+120}
  message=encode(b'{"alg":"RS256","typ":"JWT"}')+'.'+encode(json.dumps(c).encode());return {'ticket':message+'.'+encode(self.auth.sign(message.encode(),padding.PKCS1v15(),hashes.SHA256())),'payload':payload}
 def test_roundtrip_replay_isolation_and_counter_contains_no_content(self):
  req=self.request('/api/cloud/items','POST',{'kind':'tasks','title':'private title','payload':{'text':'private body'}})
  status,result=self.gateway.handle(req);self.assertEqual(status,201);self.assertEqual(self.gateway.handle(req)[1]['item']['id'],result['item']['id'])
  claims=json.loads(decode(result['receipt'].split('.')[1]));self.assertEqual(claims['tasks'],1);self.assertNotIn('private',json.dumps(claims))
  self.assertEqual(self.gateway.handle(self.request('/api/cloud/items',uid=str(uuid4())))[1]['items'],[])
  id=result['item']['id'];self.assertEqual(self.gateway.handle(self.request('/api/cloud/items/'+id,'DELETE',{'version':result['item']['version']}))[0],200)
  self.assertEqual(self.gateway.handle(self.request('/api/cloud/items'))[1]['items'],[])
 def test_tampering_and_other_purpose_are_rejected(self):
  req=self.request('/api/cloud/items');req['payload']=req['payload'].replace('GET','DELETE')
  with self.assertRaises(Error):self.gateway.handle(req)
  with self.assertRaises(Error):self.gateway.handle(self.request('/api/admin/overview'))
