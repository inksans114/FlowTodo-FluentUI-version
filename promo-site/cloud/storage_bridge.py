"""Outbound HTTPS only; the queue contains authenticated encrypted RPC envelopes."""
import hashlib
import hmac
import json
import logging
import os
import threading
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

ORIGIN='https://app.cheemsdoge.xyz'
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):return None
def run_worker(kind,config):
    key=bytes.fromhex(config['storageKey'])
    opener=urllib.request.build_opener(NoRedirect())
    def api(path,body):
        body.update(at=int(time.time()*1000),nonce=str(uuid4()))
        raw=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode()
        sig=hmac.new(key,b'flowtodo-storage-bridge-v1\n'+path.encode()+b'\n'+raw,hashlib.sha256).hexdigest()
        request=urllib.request.Request(ORIGIN+path,data=raw,headers={'Content-Type':'application/json','X-FlowTodo-Bridge':sig,'User-Agent':'FlowTodo/1.0 (Storage Bridge; +https://app.cheemsdoge.xyz)'})
        with opener.open(request,timeout=35) as response:return json.load(response)
    while True:
        try:
            job=api('/api/storage/bridge/poll',{'kind':kind})
            if job.get('idle'):continue
            raw=json.dumps(job['envelope'],separators=(',',':')).encode()
            request=urllib.request.Request('http://127.0.0.1:4191/rpc',data=raw,headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(request,timeout=260) as response:envelope=json.load(response)
            # Only retry delivering the encrypted result; never repeat an AI call.
            for attempt in range(3):
                try:api('/api/storage/bridge/result',{'id':job['id'],'envelope':envelope});break
                except Exception:
                    if attempt==2:raise
                    time.sleep(1)
        except Exception as error:
            logging.warning('Bridge %s unavailable (%s); retrying',kind,type(error).__name__)
            time.sleep(3)

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
    config=json.loads(Path(os.environ.get('FLOWTODO_CLOUD_CONFIG','/etc/flowtodo-cloud/credentials.json')).read_text())
    for kind in ['records','records','ai']:threading.Thread(target=run_worker,args=(kind,config),daemon=True).start()
    threading.Event().wait()
