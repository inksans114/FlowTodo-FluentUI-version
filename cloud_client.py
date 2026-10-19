"""Desktop account transport. Relay credentials never enter this process."""
from __future__ import annotations
import urllib.parse
import json
import hashlib
import os
import sys
import threading
from types import SimpleNamespace
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

ORIGIN = "https://app.cheemsdoge.xyz"
ACCOUNT_ORIGIN = "https://dashboard.cheemsdoge.xyz:24336"


class CloudError(RuntimeError):
    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CloudError("账户服务发生意外跳转，请稍后重试。")


class SessionVault:
    """DPAPI ciphertext on Windows; memory-only elsewhere until an OS vault is available."""
    def __init__(self, path, protector=None):
        self.path = Path(path)
        self.protector = protector
        if protector is None and sys.platform == "win32":
            import win32crypt
            self.protector = (
                lambda data: win32crypt.CryptProtectData(data, "FlowTodo account", None, None, None, 1),
                lambda data: win32crypt.CryptUnprotectData(data, None, None, None, 1)[1],
            )
        self.memory = {}
        if self.protector and self.path.exists():
            try:
                self.memory = json.loads(self.protector[1](self.path.read_bytes()))
            except Exception:
                self.memory = {}  # A vault copied from another OS user is not reusable.

    def save(self, value):
        self.memory = dict(value)
        if not self.protector:
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + "." + uuid4().hex + ".tmp")
        try:
            temporary.write_bytes(self.protector[0](json.dumps(value).encode()))
            if sys.platform != "win32":
                os.chmod(temporary, 0o600)
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
        return True

    def clear(self):
        self.memory = {}
        self.path.unlink(missing_ok=True)


class CloudClient:
    def __init__(self, vault, opener=None):
        self.vault = vault
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.lock = threading.RLock()
        self.session_generation = 0

    @property
    def logged_in(self):
        return bool(self.vault.memory.get("accessToken"))

    def request(self, path, body=None, method=None, timeout=25, origin=None):
        if not path.startswith("/api/") or ".." in path or "#" in path:
            raise ValueError("Invalid account endpoint")
        origin=origin or self.vault.memory.get('origin',ORIGIN)
        if origin not in (ORIGIN,ACCOUNT_ORIGIN):raise ValueError('Invalid account origin')
        if path=='/api/account' and self.vault.memory.get('pendingAIReceipt'):
            receipt=self.vault.memory['pendingAIReceipt']
            try:
                self.request('/api/ai/receipt',{'receipt':receipt})
                with self.lock:
                    updated=dict(self.vault.memory);updated.pop('pendingAIReceipt',None);self.vault.save(updated)
            except CloudError as error:
                if error.status==400:
                    with self.lock:
                        updated=dict(self.vault.memory);updated.pop('pendingAIReceipt',None);self.vault.save(updated)
        if (path.startswith('/api/cloud/') and path not in ('/api/cloud/ticket','/api/cloud/receipt')) or path=='/api/account/avatar':
            if self.request('/api/config',origin=ORIGIN).get('cloudDirectEnabled'):
                return self.cloud_direct(path,body,method or ('GET' if body is None else 'POST'))
        headers = {"Content-Type": "application/json", "Origin": origin, "X-FlowTodo-Request": "1", "User-Agent":"FlowTodo/1.0 (Desktop; +https://app.cheemsdoge.xyz)"}
        with self.lock:
            access = self.vault.memory.get("accessToken")
        if access and origin==self.vault.memory.get('origin',ORIGIN):
            headers["Authorization"] = "Bearer " + access
        request = urllib.request.Request(origin + path,
            data=None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers, method=method or ("GET" if body is None else "POST"))
        try:
            with self.opener.open(request, timeout=timeout) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise CloudError("云端返回的数据过大，请分批同步。")
                result=json.loads(raw)
                if path=='/api/account' and result.get('cloud',{}).get('location')=='xiangyang-direct':
                    try:
                        summary=self.cloud_direct('/api/cloud/summary',None,'GET')
                        summary['usage']['aiCalls']=result['usage']['aiCalls']
                        result.update(summary);result['cloud']['location']='xiangyang-direct'
                        result['user']['avatarUrl']=result['avatar'].get('data','')
                    except CloudError as error:
                        result['cloud'].update(connected=False,error=str(error))
                return result
        except urllib.error.HTTPError as error:
            try:
                value = json.loads(error.read(4096))
                message = value.get("error", "账户服务暂时不可用。")
            except (ValueError, TypeError):
                message = "账户服务暂时不可用。"
            if error.code == 401 and access and origin==self.vault.memory.get('origin',ORIGIN):
                with self.lock:
                    if access == self.vault.memory.get('accessToken'):
                        self.clear_session()
            raise CloudError(str(message), error.code) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise CloudError("暂时无法连接云端。本地数据仍然保留，请稍后重试。") from None
        except (ValueError, TypeError):
            raise CloudError("云端响应异常，请稍后重试。") from None

    def begin_login(self, name="FlowTodo 桌面端"):
        return self.request("/api/device/start", {"name": name})

    def native_start(self,email):
        # Pilot uses the currently reachable account service; migration is announced in config.
        config=self.request('/api/config',origin=ORIGIN)
        origin=ACCOUNT_ORIGIN if config.get('identityBroker') else ORIGIN
        pending=self.request('/api/device/start',{'name':'FlowTodo 桌面端'},origin=origin)
        self.request('/api/native/send-code',{'email':email,'deviceCode':pending['deviceCode']},origin=origin)
        pending['origin']=origin
        return pending

    def native_verify(self,email,code,device,origin=ORIGIN):
        with self.lock:generation=self.session_generation
        result=self.request('/api/native/verify',{'email':email,'code':code,'deviceCode':device},origin=origin)
        if not result.get('accessToken'):raise CloudError('登录响应异常，请重试。')
        with self.lock:
            if generation!=self.session_generation:raise CloudError('登录请求已取消。')
            self.vault.save({**result,'origin':origin})
        return result

    def poll_login(self, code):
        with self.lock:generation=self.session_generation
        result = self.request("/api/device/poll", {"deviceCode": code})
        if result.get("accessToken"):
            with self.lock:
                if generation!=self.session_generation:raise CloudError('登录请求已取消。')
                persisted = self.vault.save(result)
            result = {"connected": True, "persisted": persisted}
        return result

    def clear_session(self):
        with self.lock:
            session = dict(self.vault.memory)
            self.session_generation += 1
            self.vault.clear()
            return session

    def revoke_session(self, session):
        if session.get('accessToken'):
            # Isolate the old credential so a delayed response cannot clear a new login.
            vault = SimpleNamespace(memory=session, clear=lambda: None)
            CloudClient(vault, self.opener).request('/api/auth/logout', {}, timeout=5)

    def logout(self):
        self.revoke_session(self.clear_session())

    def list_records(self, trash=False):
        rows, cursor = [], ""
        for _ in range(60):
            result = self.request("/api/cloud/items?trash=" + ("1" if trash else "0") + cursor)
            rows.extend(result["items"])
            if not result.get("next"):
                return rows
            cursor = "&after=" + urllib.parse.quote(result["next"])
        raise CloudError("云端记录过多，请先在网站整理。")

    def cloud_direct(self,path,body,method):
        b={'requestId':str(uuid4()),'path':path,'method':method,'body':body}
        payload=json.dumps(b,ensure_ascii=False,separators=(',',':'))
        proof=self.request('/api/cloud/ticket',{'requestId':b['requestId'],'payloadHash':hashlib.sha256(payload.encode()).hexdigest()})
        endpoint='http://103.236.91.136:24336/api/cloud/direct'
        if proof.get('endpoint')!=endpoint:raise CloudError('存储地址无效。')
        req=urllib.request.Request(endpoint,data=json.dumps({'ticket':proof['ticket'],'payload':payload},ensure_ascii=False).encode(),headers={'Content-Type':'application/json','User-Agent':'FlowTodo/1.0'},method='POST')
        try:
            with self.opener.open(req,timeout=35) as response:
                raw=response.read(2_000_001)
                if len(raw)>2_000_000:raise CloudError('记录过多，请分批同步。')
                result=json.loads(raw)
        except urllib.error.HTTPError as error:
            try:message=json.loads(error.read(4096)).get('error','存储服务暂时不可用。')
            except ValueError:message='存储服务暂时不可用。'
            raise CloudError(message,error.code) from None
        except (urllib.error.URLError,TimeoutError,OSError):raise CloudError('暂时无法连接襄阳存储，本地数据仍然保留。') from None
        receipt=result.pop('receipt',None)
        if receipt:
            try:self.request('/api/cloud/receipt',{'receipt':receipt})
            except CloudError:pass  # Next summary supplies a fresh authoritative counter.
        return result

    def ai_chat(self, messages, max_tokens=1800, temperature=0.7):
        body={"requestId":str(uuid4()),"messages":messages,"maxTokens":max_tokens,"temperature":temperature}
        config=self.request('/api/config',origin=ORIGIN)
        if not config.get('aiDirectEnabled'):
            return self.request('/api/ai/chat',body,timeout=300)
        payload=json.dumps(body,ensure_ascii=False,separators=(',',':'))
        proof=self.request('/api/ai/ticket',{'requestId':body['requestId'],'payloadHash':hashlib.sha256(payload.encode()).hexdigest()})
        endpoint='http://103.236.91.136:24336/api/ai/direct'
        if proof.get('endpoint')!=endpoint:raise CloudError('官方通道地址无效。')
        req=urllib.request.Request(endpoint,data=json.dumps({'ticket':proof['ticket'],'payload':payload},ensure_ascii=False).encode(),headers={'Content-Type':'application/json','User-Agent':'FlowTodo/1.0'},method='POST')
        try:
            with self.opener.open(req,timeout=300) as response:
                raw=response.read(2_000_001)
                if len(raw)>2_000_000:raise CloudError('官方回复过长。')
                result=json.loads(raw)
        except urllib.error.HTTPError as e:
            try:
                error_data=json.loads(e.read(4096));message=error_data.get('error','官方通道暂时不可用。')
                self._accept_ai_receipt(error_data.pop('receipt',None))
            except ValueError:message='官方通道暂时不可用。'
            raise CloudError(message,e.code) from None
        except (urllib.error.URLError,TimeoutError,OSError):raise CloudError('暂时无法直连襄阳官方通道，请稍后重试。') from None
        self._accept_ai_receipt(result.pop('receipt',None))
        return result

    def _accept_ai_receipt(self,receipt):
        if receipt:
            try:self.request('/api/ai/receipt',{'receipt':receipt})
            except CloudError:
                with self.lock:self.vault.save({**self.vault.memory,'pendingAIReceipt':receipt})
