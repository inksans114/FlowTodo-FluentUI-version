import io,json,hashlib,unittest
from cloud_client import CloudClient,CloudError
class Vault:
 def __init__(self):self.memory={'accessToken':'local-session'}
 def save(self,v):self.memory=dict(v)
class Response(io.BytesIO):
 def __enter__(self):return self
 def __exit__(self,*a):self.close()
class ClientTest(unittest.TestCase):
 def test_storage_content_goes_only_to_xiangyang_and_cf_receives_hash_and_receipt(self):
  calls=[];requests=[]
  class Opener:
   def open(self,request,timeout):requests.append(request);return Response(json.dumps({'items':[{'title':'private note'}],'receipt':'signed-counters'}).encode())
  class Client(CloudClient):
   def request(self,path,body=None,**kwargs):
    calls.append((path,body))
    if path=='/api/cloud/ticket':return {'ticket':'bound','endpoint':'http://103.236.91.136:24336/api/cloud/direct'}
    return {'ok':True}
  result=Client(Vault(),Opener()).cloud_direct('/api/cloud/items',None,'GET')
  self.assertEqual(result['items'][0]['title'],'private note');self.assertNotIn('private note',json.dumps(calls))
  self.assertFalse(requests[0].has_header('Authorization'));self.assertFalse(requests[0].has_header('Cookie'))
  self.assertEqual(calls[-1],('/api/cloud/receipt',{'receipt':'signed-counters'}))
 def test_direct_call_contains_no_login_token_and_reports_signed_receipt(self):
  vault=Vault();calls=[];requests=[]
  class Opener:
   def open(self,request,timeout):
    requests.append(request);return Response(json.dumps({'choices':[{'message':{'content':'OK'}}],'receipt':'server-signed'}).encode())
  class Client(CloudClient):
   def request(self,path,body=None,**kwargs):
    calls.append((path,body))
    if path=='/api/config':return {'aiDirectEnabled':True}
    if path=='/api/ai/ticket':return {'ticket':'request-bound','endpoint':'http://103.236.91.136:24336/api/ai/direct'}
    if path=='/api/ai/receipt':return {'ok':True}
  result=Client(vault,Opener()).ai_chat([{'role':'user','content':'测试'}])
  self.assertEqual(result['choices'][0]['message']['content'],'OK');self.assertNotIn('receipt',result)
  self.assertFalse(requests[0].has_header('Authorization'));self.assertFalse(requests[0].has_header('Cookie'))
  envelope=json.loads(requests[0].data);self.assertEqual(calls[1][1]['payloadHash'],hashlib.sha256(envelope['payload'].encode()).hexdigest());self.assertEqual(calls[-1],('/api/ai/receipt',{'receipt':'server-signed'}))
 def test_rejects_unexpected_destination(self):
  class Client(CloudClient):
   def request(self,path,body=None,**kwargs):
    if path=='/api/config':return {'aiDirectEnabled':True}
    return {'ticket':'anything','endpoint':'http://evil.example/api/ai/direct'}
  with self.assertRaises(CloudError):Client(Vault()).ai_chat([])
if __name__=='__main__':unittest.main()
