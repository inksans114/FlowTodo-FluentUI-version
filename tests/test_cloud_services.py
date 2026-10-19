import base64
import copy
import json
import secrets
import sys
import tempfile
import time
import unittest
from pathlib import Path
from uuid import uuid4
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'promo-site/cloud'))
from server_storage import Store, Error, RPC
from cloud_sync import SyncEngine, fingerprint
from ai_service_settings import switch_service, public_settings

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'store.sqlite');self.uid=str(uuid4());self.other=str(uuid4())
    def tearDown(self):self.temp.cleanup()
    def call(self,path,method='GET',body=None,uid=None):return self.store.handle(uid or self.uid,'free',path,method,body or {})
    def test_record_ownership_versions_and_duplicate_upload(self):
        body={'kind':'tasks','title':'私人待办','payload':{'_syncUid':'same','record':{'done':False}}}
        _,result=self.call('/api/cloud/items','POST',body);item=result['item']
        self.assertEqual(self.call('/api/cloud/items','POST',body)[1]['item']['id'],item['id'])
        self.assertEqual(self.call('/api/cloud/items',uid=self.other)[1]['items'],[])
        with self.assertRaises(Error) as caught:self.call('/api/cloud/items/'+item['id'],'PATCH',{'title':'不应覆盖','payload':{},'version':0})
        self.assertEqual(caught.exception.status,409)
        with self.assertRaises(Error) as caught:self.call('/api/cloud/items/'+item['id'],'DELETE',{'version':1},uid=self.other)
        self.assertEqual(caught.exception.status,404)
        self.call('/api/cloud/items/'+item['id'],'DELETE',{'version':1})
        self.assertEqual(self.call('/api/cloud/items')[1]['items'],[])
        self.call('/api/cloud/items/'+item['id']+'/restore','POST',{'version':2})
        self.assertEqual(self.call('/api/cloud/items')[1]['items'][0]['version'],3)
    def test_free_quota(self):
        for i in range(30):self.call('/api/cloud/items','POST',{'kind':'tasks','title':str(i),'payload':{}})
        with self.assertRaises(Error):self.call('/api/cloud/items','POST',{'kind':'tasks','title':'超额','payload':{}})
    def test_avatar_rejects_svg_and_conflicting_revision(self):
        with self.assertRaises(Error):self.call('/api/account/avatar','PUT',{'data':'data:image/svg+xml;base64,PHN2Zz4=','revision':0})
        self.call('/api/account/avatar','PUT',{'data':'','revision':0})
        with self.assertRaises(Error):self.call('/api/account/avatar','PUT',{'data':'','revision':0})
        self.assertEqual(self.call('/api/account/avatar')[1]['revision'],1)
    def test_rpc_encryption_tampering_and_replay(self):
        key=secrets.token_bytes(32);rpc=RPC({'database':str(Path(self.temp.name)/'rpc.sqlite'),'storageKey':key.hex()});aes=AESGCM(key)
        raw={'id':str(uuid4()),'at':int(time.time()*1000),'user':{'id':self.uid,'plan':'free'},'path':'/api/cloud/summary','method':'GET','body':{}}
        nonce=secrets.token_bytes(12);cipher=aes.encrypt(nonce,json.dumps(raw).encode(),b'flowtodo-storage-request-v1')
        envelope={'nonce':base64.b64encode(nonce).decode(),'data':base64.b64encode(cipher).decode()};out=rpc.execute(envelope)
        result=json.loads(aes.decrypt(base64.b64decode(out['nonce']),base64.b64decode(out['data']),b'flowtodo-storage-response-v1'))
        self.assertEqual(result['id'],raw['id']);self.assertEqual(result['status'],200)
        with self.assertRaises(Exception):rpc.execute(envelope)
        envelope['data']=base64.b64encode(cipher[:-1]+bytes([cipher[-1]^1])).decode()
        with self.assertRaises(Exception):rpc.execute(envelope)

class SyncTests(unittest.TestCase):
    def test_adopted_identity_conflict_persists_until_explicit_resolution(self):
        with tempfile.TemporaryDirectory() as temp:
            engine=SyncEngine(Path(temp)/'links.json');local={'key':'tasks:a','kind':'tasks','title':'本地修改','payload':{'_syncUid':'a'}}
            remote=dict(local,id='a',version=2,title='云端修改')
            class Client:
                def list_records(self,trash=False):return [] if trash else [remote]
                def request(self,*args):raise AssertionError('Must retain both copies')
            for _ in range(2):
                result=engine.run(Client(),[local]);self.assertEqual(len(result['conflicts']),1);engine.save(result['links'])
    def test_duplicate_upload_response_never_acknowledges_different_contents(self):
        with tempfile.TemporaryDirectory() as temp:
            engine=SyncEngine(Path(temp)/'links.json');local={'key':'tasks:a','kind':'tasks','title':'本地修改','payload':{'_syncUid':'a'}}
            class Client:
                def list_records(self,trash=False):return []
                def request(self,*args):return {'item':dict(local,id='a',version=2,title='另一端修改')}
            result=engine.run(Client(),[local],['tasks:a']);self.assertEqual(result['uploaded'],0);self.assertEqual(len(result['conflicts']),1);self.assertEqual(result['pulls'],[])
    def test_remote_and_local_edits_conflict_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            engine=SyncEngine(Path(temp)/'links.json');original={'key':'tasks:a','kind':'tasks','title':'原始','payload':{}}
            engine.save({'tasks:a':{'id':'a','version':1,'kind':'tasks','base':fingerprint(original)}})
            class Client:
                def list_records(self,trash=False):return [] if trash else [dict(original,id='a',version=2,title='云端修改')]
                def request(self,*args):raise AssertionError('Must not overwrite')
            local=dict(original,title='本地修改');result=engine.run(Client(),[local]);self.assertEqual(len(result['conflicts']),1);self.assertEqual(result['pulls'],[])
    def test_failed_batch_keeps_acknowledged_upload_but_not_unapplied_pull(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'links.json';engine=SyncEngine(path);row={'key':'tasks:a','kind':'tasks','title':'原始','payload':{}}
            engine.save({'tasks:a':{'id':'a','version':1,'kind':'tasks','base':fingerprint(row)}})
            class Client:
                def list_records(self,trash=False):return [] if trash else [dict(row,id='a',version=2,title='新标题')]
                def request(self,path,body):
                    if body['title']=='fail':raise RuntimeError('Disconnected')
                    return {'item':{'id':'b','version':1}}
            new=dict(row,key='tasks:b',title='success');bad=dict(row,key='tasks:c',title='fail')
            with self.assertRaises(RuntimeError):engine.run(Client(),[row,new,bad],['tasks:b','tasks:c'])
            saved=SyncEngine(path).links;self.assertEqual(saved['tasks:a']['version'],1);self.assertIn('tasks:b',saved)
    def test_official_mode_has_no_client_key_and_preserves_custom(self):
        original={'aiServiceMode':'custom','aiApiKey':'user-key','aiBaseUrl':'https://private.example','aiModel':'custom-model'}
        official=switch_service(original,'official');self.assertEqual(official['aiApiKey'],'');self.assertNotIn('aiApiKey',public_settings(official))
        self.assertEqual(switch_service(official,'custom')['aiApiKey'],'user-key')

if __name__=='__main__':unittest.main()
