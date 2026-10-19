import sys
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'promo-site/cloud'))
from official_routing import OfficialRelay
from server_storage import Store,Error
from relay_pricing import price_bounds

class RotationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'db.sqlite')
        self.uid=str(uuid4());self.grant=str(uuid4())
        routes=[{'groupId':gid,'model':model,'pricingVerified':True,'maxInputUsdPerMillion':1,'maxOutputUsdPerMillion':1} for gid,model in [(7,'glm-flash'),(4,'deepseek-flash'),(5,'deepseek-flash'),(6,'glm-flash')]]
        self.relay=OfficialRelay({'relayVaultKey':'01'*32,'officialRoutes':routes,'pricingVerified':True},self.store)
        self.secret={'routeKeys':{str(g):{'id':g,'key':'private-key-'+str(g)} for g in (7,4,5,6)}}
        with self.store.connect() as db:db.execute("INSERT INTO relay_users VALUES(?,?,?,?,?,'active')",(self.uid,self.relay.pack(self.secret),self.grant,0.01,time.time()+1000))
        self.relay.api=lambda path,**kw: {'rate_multiplier':1} if '/groups/' in path else {'items':[]} if 'channels?page' in path else {'found':True,'input_price':0.000001,'output_price':0.000001}
        self.calls=[]
    def tearDown(self):self.temp.cleanup()
    def body(self,id=None):return {'requestId':id or str(uuid4()),'messages':[{'role':'user','content':'hello'}],'maxTokens':100}
    def ok(self,key,route,*args):
        self.calls.append(route['groupId']);return {'choices':[{'message':{'content':'answer '+key}}],'usage':{'total_tokens':10,'api_key':'secret'}}
    def test_rotation_and_no_key_in_response(self):
        self.relay.upstream=self.ok
        for _ in range(4):
            _,reply=self.relay.chat(self.uid,self.body());self.assertNotIn('private-key',str(reply));self.assertNotIn('api_key',reply['usage'])
        self.assertEqual(self.calls,[7,4,5,6])
    def test_three_failed_groups_reach_fourth(self):
        def upstream(key,route,*args):
            if route['groupId']!=6:
                self.calls.append(route['groupId']);raise urllib.error.HTTPError('http://localhost',503,'unavailable',{},None)
            return self.ok(key,route,*args)
        self.relay.upstream=upstream;self.relay.chat(self.uid,self.body());self.assertEqual(self.calls,[7,4,5,6])
    def test_timeout_does_not_retry_and_reserves_money(self):
        def upstream(key,route,*args):self.calls.append(route['groupId']);raise TimeoutError()
        self.relay.upstream=upstream
        with self.assertRaises(Error):self.relay.chat(self.uid,self.body())
        self.assertEqual(self.calls,[7])
        with self.store.connect() as db:self.assertEqual(db.execute('SELECT status FROM ai_spend').fetchone()[0],'uncertain')
    def test_shared_cap_and_duplicate_request(self):
        self.relay.upstream=self.ok;body=self.body();self.relay.chat(self.uid,body)
        with self.assertRaises(Error) as caught:self.relay.chat(self.uid,body)
        self.assertEqual(caught.exception.status,409)
        with self.store.connect() as db:db.execute('UPDATE relay_users SET budget=0.000001 WHERE user_id=?',(self.uid,))
        with self.assertRaises(Error) as caught:self.relay.chat(self.uid,self.body())
        self.assertEqual(caught.exception.status,403);self.assertEqual(len(self.calls),1)
    def test_price_drift_skips_only_bad_route(self):
        previous=self.relay.ceiling
        def ceiling(route,*args):
            if route['groupId']==7:raise Error(503,'price changed')
            return previous(route,*args)
        self.relay.ceiling=ceiling;self.relay.upstream=self.ok
        self.relay.chat(self.uid,self.body());self.assertEqual(self.calls,[4])
    def test_custom_channel_cache_and_time_prices_bound_cost(self):
        def api(path):
            if '/groups/' in path:return {'rate_multiplier':0.15,'status':'active'}
            if 'model-pricing?' in path:return {'found':True,'input_price':0.0000002,'output_price':0.0000006}
            return {'items':[{'group_ids':[7],'status':'active','model_pricing':[{'models':['glm-*'],'billing_mode':'token','cache_write_price':0.000002,'output_price':0.000004,'time_pricing':{'periods':[{'multiplier':2}]}}]}]}
        inp,out=price_bounds(api,7,'glm-flash');self.assertAlmostEqual(inp,0.6);self.assertAlmostEqual(out,1.2)

if __name__=='__main__':unittest.main()
