import base64,hashlib,json,tempfile,time,unittest,sys
from pathlib import Path
from uuid import uuid4
from unittest.mock import Mock
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa,padding
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'promo-site/cloud'))
from ai_direct import DirectAI,encode
from server_storage import Store,Error

class DirectAITest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
  self.auth=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  receipt=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  private=root/'receipt.pem';private.write_bytes(receipt.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
  self.store=Store(root/'store.sqlite');self.gateway=DirectAI({'aiTicketPublic':self.auth.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode(),'aiReceiptPrivatePath':str(private),'relayVaultKey':'12'*32},self.store)
  self.gateway.relay=Mock();self.gateway.relay.handle.side_effect=lambda uid,path,b:(200,{'choices':[{'message':{'content':'OK'}}]})
  self.claims={'iss':'https://app.cheemsdoge.xyz','aud':'flowtodo-xiangyang','purpose':'ai-call','sub':str(uuid4()),'grant':str(uuid4()),'requestId':str(uuid4()),'plan':'free','limit':5,'budgetUsd':.02,'grantExpires':int((time.time()+86400)*1000),'iat':int(time.time()),'exp':int(time.time())+120}
 def tearDown(self):self.temp.cleanup()
 def request(self,**changes):
  c={**self.claims,**changes};payload=json.dumps({'requestId':c['requestId'],'messages':[{'role':'user','content':'hi'}],'maxTokens':2},separators=(',',':'));c['payloadHash']=hashlib.sha256(payload.encode()).hexdigest()
  message=encode(b'{"alg":"RS256","typ":"JWT"}')+'.'+encode(json.dumps(c).encode())
  ticket=message+'.'+encode(self.auth.sign(message.encode(),padding.PKCS1v15(),hashes.SHA256()))
  return {'ticket':ticket,'payload':payload}
 def test_proof_is_request_bound_and_quota_cannot_be_inflated(self):
  request=self.request();request['payload']+=' '
  with self.assertRaises(Error):self.gateway.handle(request)
  with self.assertRaises(Error):self.gateway.handle(self.request(limit=300))
  with self.assertRaises(Error):self.gateway.handle(self.request(exp=int(time.time())-1))
  self.gateway.relay.handle.assert_not_called()
 def test_replay_returns_same_answer_without_second_model_call(self):
  request=self.request();status,result=self.gateway.handle(request);self.assertEqual(status,200)
  self.assertIn('receipt',result);self.assertEqual(self.gateway.relay.handle.call_count,2)
  self.assertEqual(self.gateway.handle(request)[1]['choices'],result['choices']);self.assertEqual(self.gateway.relay.handle.call_count,2)
 def test_small_server_clock_skew_is_bounded(self):
  request=self.request(iat=int(time.time())+48,exp=int(time.time())+120)
  self.assertEqual(self.gateway.verify(request['ticket'],request['payload'])[0]['limit'],5)
  with self.assertRaises(Error):
   request=self.request(iat=int(time.time())+90,exp=int(time.time())+180);self.gateway.verify(request['ticket'],request['payload'])
 def test_authoritative_server_limit(self):
  uid=self.claims['sub'];grant=self.claims['grant']
  with self.store.connect() as db:
   for _ in range(5):db.execute("INSERT INTO direct_ai_requests VALUES(?,?,?,'hash','complete','{}',?)",(uid,grant,str(uuid4()),time.time()-120))
  with self.assertRaises(Error) as ctx:self.gateway.handle(self.request())
  self.assertEqual(ctx.exception.status,403);self.gateway.relay.handle.assert_not_called()
if __name__=='__main__':unittest.main()
