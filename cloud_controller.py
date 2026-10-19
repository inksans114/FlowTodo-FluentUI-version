"""Qt account jobs, encrypted desktop sessions and explicit record synchronization."""
from __future__ import annotations
import base64
import copy
import json
import re
import time
from pathlib import Path
from PySide6.QtCore import QObject, QThread, QTimer, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from cloud_client import CloudClient, CloudError, SessionVault, ORIGIN
from cloud_sync import SyncEngine, fingerprint
from ai_library import write_state

class Job(QThread):
    result=Signal(object)
    error=Signal(str)
    def __init__(self,call,parent):super().__init__(parent);self.call=call
    def run(self):
        try:self.result.emit(self.call())
        except CloudError as error:self.error.emit(str(error))
        except Exception:self.error.emit('操作暂时无法完成，本地记录已保留，请稍后重试。')

class CloudController(QObject):
    def __init__(self,backend):
        super().__init__(backend);self.backend=backend;self.directory=Path(backend.data_dir)
        self.client=CloudClient(SessionVault(self.directory/'cloud-session.vault'))
        self.busy=False;self.error='';self.status='尚未登录';self.pending=None;self.native_pending=None;self.native_email='';self.native_sent=0;self.cache={};self.conflicts=[];self.last_sync='';self.avatar_dirty=False;self.profile_dirty=False;self.jobs=[];self.generation=0
        try:self.cache=json.loads((self.directory/'cloud-account-cache.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
        if not isinstance(self.cache,dict):self.cache={}
        self.avatar_base=(self.cache.get('avatar') or {}).get('revision',0)
        try:
            pending=json.loads((self.directory/'cloud-pending-profile.json').read_text(encoding='utf-8'))
            if pending.get('uid')==self.account().get('id'):
                self.avatar_dirty=bool(pending.get('avatarDirty'));self.avatar_base=pending.get('avatarBase',self.avatar_base)
        except (OSError,ValueError):pass
        self.poll=QTimer(self);self.poll.setInterval(5000);self.poll.timeout.connect(self.poll_login)
        self.pending_vault=SessionVault(self.directory/'cloud-login-pending.vault')
        saved=self.pending_vault.memory
        if saved.get('deadline',0)>time.time() and re.fullmatch('[a-f0-9]{64}',str(saved.get('deviceCode',''))) and re.fullmatch('[A-F0-9]{10}',str(saved.get('userCode',''))):
            self.pending=dict(saved);self.poll.start()
        else:self.pending_vault.clear()
        self.refresh_timer=QTimer(self);self.refresh_timer.setInterval(300000);self.refresh_timer.timeout.connect(self.refresh);self.refresh_timer.start()
        self.auto_timer=QTimer(self);self.auto_timer.setInterval(30000);self.auto_timer.timeout.connect(self.auto_sync);self.auto_timer.start()
        self.auto_debounce=QTimer(self);self.auto_debounce.setSingleShot(True);self.auto_debounce.setInterval(1500);self.auto_debounce.timeout.connect(self.auto_sync)
        for name in ('tasksChanged','groupsChanged','settingsChanged'):
            signal=getattr(backend,name,None)
            if signal is not None:signal.connect(self.auto_debounce.start)
        QTimer.singleShot(1000,self.refresh)
    def changed(self):self.backend.accountChanged.emit()
    def save_pending(self):
        write_state(self.directory/'cloud-pending-profile.json',{'uid':self.account().get('id'),'avatarDirty':self.avatar_dirty,'avatarBase':self.avatar_base})
    def job(self,call,done):
        if self.busy:return False
        self.busy=True;self.error='';self.changed();generation=self.generation
        job=Job(call,self);self.jobs.append(job)
        def success(result):
            if generation!=self.generation:return
            self.busy=False
            try:done(result)
            except Exception:self.error='云端返回的数据无法导入，本地记录已保留。'
            self.changed()
        def failed(message):
            if generation!=self.generation:return
            self.busy=False;self.error=message;self.status='连接暂时中断' if self.client.logged_in else '请重新登录';self.changed()
        job.result.connect(success);job.error.connect(failed)
        job.finished.connect(lambda: self.jobs.remove(job) if job in self.jobs else None)
        job.finished.connect(job.deleteLater);job.start();return True
    def account(self):return self.cache.get('user') or {}
    def logged_in(self):return self.client.logged_in and bool(self.account().get('id'))
    def cache_account(self,data):
        if self.profile_dirty:data['user']['name']=self.account().get('name',data['user']['name'])
        self.cache=data;write_state(self.directory/'cloud-account-cache.json',data)
        avatar=data.get('avatar') or {}
        if not self.avatar_dirty and not avatar.get('unavailable'):
            self.avatar_base=avatar.get('revision',0)
            target=self.avatar_path()
            if avatar.get('data','').startswith('data:image/png;base64,'):
                raw=base64.b64decode(avatar['data'].split(',')[1],validate=True)
                if len(raw)<=131072:
                    temp=target.with_suffix('.tmp');temp.write_bytes(raw);temp.replace(target)
            else:target.unlink(missing_ok=True)
        self.status='已登录；存储暂时离线' if not data.get('cloud',{}).get('connected',False) else '已连接云端';self.backend.settingsChanged.emit()
        self.auto_debounce.start()
    def avatar_path(self):
        uid=self.account().get('id','')
        if not re.fullmatch(r'[a-f0-9-]{36}',uid):return self.directory/'cloud-avatar-none.png'
        return self.directory/('cloud-avatar-'+uid+'.png')
    def view(self):
        rows=getattr(self,'cloud_library',[]) if self.logged_in() and getattr(self,'cloud_library_uid',None)==self.account().get('id') else []
        return {**self._view(),'library':rows,'trash':getattr(self,'cloud_trash',False)}
    def _view(self):
        return {'loggedIn':self.logged_in(),'busy':self.busy,'autoSync':bool(getattr(self.backend,'settings_database',{}).get('cloudAutoSync',True)),'status':self.status,'error':self.error,'codeSentAt':self.native_sent,'loginEmail':self.native_email,'userCode':self.pending.get('userCode','') if self.pending else '', 'lastSync':self.last_sync,'conflicts':[{'key':x['key'],'title':x['title'],'reason':x['reason']} for x in self.conflicts],'account':self.cache if self.logged_in() else {}}
    def send_code(self,email):
        email=str(email).strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[a-zA-Z]{2,}',email) or len(email)>254:
            self.error='请输入有效邮箱。';self.changed();return
        if self.busy or time.time()-self.native_sent<60:return
        def ready(value):
            self.native_pending=value;self.native_email=email;self.native_sent=time.time();self.status='验证码已发送，请查看邮箱'
        self.job(lambda:self.client.native_start(email),ready)
    def sign_in(self,email,code):
        email=str(email).strip().lower();code=str(code).strip()
        if not self.native_pending or email!=self.native_email:
            self.error='请先为这个邮箱获取验证码。';self.changed();return
        if not re.fullmatch('[0-9]{6}',code):self.error='请输入六位验证码。';self.changed();return
        def ready(_):
            self.native_pending=None;self.cache={};self.conflicts=[];self.avatar_dirty=False;self.profile_dirty=False;self.status='登录成功';QTimer.singleShot(0,self.refresh)
        self.job(lambda:self.client.native_verify(email,code,self.native_pending['deviceCode'],self.native_pending['origin']),ready)
    def start_login(self):
        if self.busy:return
        self.generation+=1;self.pending=None;self.poll.stop()
        def ready(value):
            self.pending=value;self.pending['deadline']=time.time()+value['expiresIn'];self.pending_vault.save(self.pending);self.status='请在官网完成注册或登录';self.poll.start();QDesktopServices.openUrl(QUrl(value['verificationUri']))
        self.job(self.client.begin_login,ready)
    def poll_login(self):
        if not self.pending or self.busy:return
        if time.time()>self.pending['deadline']:
            self.poll.stop();self.pending=None;self.pending_vault.clear();self.error='登录请求已到期，请重新开始。';self.changed();return
        def ready(value):
            if value.get('connected'):
                self.cache={};self.conflicts=[];self.avatar_dirty=False;self.profile_dirty=False;self.save_pending()
                self.pending=None;self.pending_vault.clear();self.poll.stop();self.status='登录成功';QTimer.singleShot(0,self.refresh)
        self.job(lambda:self.client.poll_login(self.pending['deviceCode']),ready)
    def wake_login(self,code):
        if not self.pending or self.pending.get('userCode')!=code or self.pending.get('deadline',0)<=time.time():return False
        self.poll_login();return True
    def refresh(self):
        if not self.client.logged_in or self.busy:return
        self.job(lambda:self.client.request('/api/account'),self.cache_account)
    def logout(self):
        session=self.client.clear_session()
        self.generation+=1;self.busy=False;self.error=''
        self.pending_vault.clear();self.native_pending=None;self.native_email='';self.native_sent=0
        self.pending=None;self.poll.stop();self.cache={};self.conflicts=[];self.avatar_dirty=False;self.profile_dirty=False
        self.cloud_library=[];self.cloud_library_uid=None;self.last_sync=''
        self.status='已退出，仍可使用本地功能'
        (self.directory/'cloud-account-cache.json').unlink(missing_ok=True)
        (self.directory/'cloud-pending-profile.json').unlink(missing_ok=True)
        self.backend.settingsChanged.emit();self.changed()
        def call():
            try:self.client.revoke_session(session)
            except CloudError:pass
        job=Job(call,self);self.jobs.append(job)
        job.finished.connect(lambda: self.jobs.remove(job) if job in self.jobs else None)
        job.finished.connect(job.deleteLater);job.start()
    def rename(self,name):
        name=str(name).strip()
        if not name or len(name)>40 or self.busy:return False
        self.profile_dirty=True;self.cache['user']['name']=name
        def done(_):self.profile_dirty=False;QTimer.singleShot(0,self.refresh)
        self.job(lambda:self.client.request('/api/account/profile',{'name':name},'PATCH'),done);return True
    def upload_avatar(self):
        if not self.logged_in():return
        if not self.avatar_dirty:self.avatar_base=(self.cache.get('avatar') or {}).get('revision',0)
        self.avatar_dirty=True;self.save_pending()
        if self.busy:QTimer.singleShot(600,self.upload_avatar);return
        target=self.avatar_path();data='data:image/png;base64,'+base64.b64encode(target.read_bytes()).decode() if target.is_file() else ''
        revision=self.avatar_base
        def done(result):self.avatar_dirty=False;self.cache['avatar']=result;self.avatar_base=result['revision'];self.save_pending();QTimer.singleShot(0,self.refresh)
        self.job(lambda:self.client.request('/api/account/avatar',{'data':data,'revision':revision},'PUT'),done)
    def replace_cloud_avatar(self):
        if self.busy or not self.logged_in():return
        target=self.avatar_path();data='data:image/png;base64,'+base64.b64encode(target.read_bytes()).decode() if target.is_file() else ''
        def call():
            current=self.client.request('/api/account/avatar')
            return self.client.request('/api/account/avatar',{'data':data,'revision':current['revision']},'PUT')
        def done(result):self.avatar_dirty=False;self.cache['avatar']=result;self.avatar_base=result['revision'];self.save_pending();QTimer.singleShot(0,self.refresh)
        self.job(call,done)
    def engine(self):return SyncEngine(self.directory/('cloud-sync-'+self.account()['id']+'.json'))
    def auto_sync(self):
        if self.busy or not self.logged_in() or self.conflicts or not getattr(self.backend,'settings_database',{}).get('cloudAutoSync',True):return False
        if not self.cache.get('user',{}).get('id'):return False
        selected=[row['key'] for row in self.backend._cloud_snapshot() if row['kind'] in ('tasks','flows')]
        return self.sync(selected,quiet=True)
    def sync(self,selected,quiet=False):
        if not self.logged_in() or self.busy:return False
        local=self.backend._cloud_snapshot();engine=self.engine()
        def done(result):
            links=result['links'];self.conflicts=result['conflicts'];imported=0
            # Import tasks first so task-flow references can resolve on a second device.
            for pull in sorted(result['pulls'],key=lambda p:0 if p['item']['kind']=='tasks' else 1):
                key=pull['key']
                current={r['key']:r for r in self.backend._cloud_snapshot()}
                if key and (key not in current or fingerprint(current[key])!=pull['expected']):
                    if key in engine.links:links[key]=engine.links[key]
                    self.conflicts.append({'key':key,'title':pull['item']['title'],'reason':'同步期间本地又有修改，两份记录均已保留。','remote':pull['item']});continue
                key=self.backend._import_cloud_record(pull['item'],key)
                if key:
                    imported+=1;updated={r['key']:r for r in self.backend._cloud_snapshot()}[key]
                    links[key]={'id':pull['item']['id'],'version':pull['item']['version'],'base':fingerprint(updated),'remoteBase':fingerprint(pull['item']),'kind':pull['item']['kind']}
            engine.save(links);self.last_sync=time.strftime('%Y-%m-%d %H:%M:%S');self.status=f'已上传 {result["uploaded"]} 条、导入 {imported} 条；{len(self.conflicts)} 条待确认'
            if not quiet:self.backend.messageRequested.emit('info','云端同步',self.status)
            if not quiet or result['uploaded'] or imported:QTimer.singleShot(0,self.refresh)
        return self.job(lambda:engine.run(self.client,local,set(selected)),done)
    def resolve(self,key,choice):
        if self.busy or not self.logged_in():return
        conflict=next((x for x in self.conflicts if x['key']==key),None)
        row=next((r for r in self.backend._cloud_snapshot() if r['key']==key),None)
        if not conflict or not row:return
        remote=conflict['remote'];engine=self.engine()
        if choice=='cloud' and remote and not remote.get('deletedAt'):
            self.backend._import_cloud_record(remote,key);current=next(r for r in self.backend._cloud_snapshot() if r['key']==key);engine.links[key].update(version=remote['version'],base=fingerprint(current),remoteBase=fingerprint(remote));engine.save(engine.links);self.conflicts.remove(conflict);self.changed();return
        if choice=='unlink':engine.links.pop(key,None);engine.save(engine.links);self.conflicts.remove(conflict);self.changed();return
        if choice!='local' or not remote:return
        def call():
            version=remote['version']
            if remote.get('deletedAt'):self.client.request('/api/cloud/items/'+remote['id']+'/restore',{'version':version});version+=1
            self.client.request('/api/cloud/items/'+remote['id'],{'title':row['title'],'payload':row['payload'],'version':version},'PATCH');return version+1
        def done(version):engine.links[key].update(version=version,base=fingerprint(row),remoteBase=fingerprint(row));engine.save(engine.links);self.conflicts.remove(conflict)
        self.job(call,done)
    def close(self):
        self.poll.stop();self.refresh_timer.stop();self.auto_timer.stop();self.auto_debounce.stop()
        for job in list(self.jobs):job.wait(30000)

    def browse_cloud(self,trash=False):
        if not self.logged_in():return
        def done(rows):self.cloud_library=rows;self.cloud_trash=bool(trash);self.cloud_library_uid=self.account().get('id')
        self.job(lambda:self.client.list_records(trash),done)

    def import_cloud(self,id=''):
        if not self.logged_in() or self.busy:return False
        if id and not re.fullmatch('[a-f0-9-]{36}',str(id)):return False
        def call():
            rows=self.client.list_records()
            if id:
                rows=[row for row in rows if row['id']==id]
                if not rows:raise CloudError('该云端记录已移走，请刷新列表。',404)
            return rows
        def done(rows):
            from cloud_import import import_downloads
            imported,skipped=import_downloads(self.backend,self.engine(),rows)
            self.status=f'已导入 {imported} 条，跳过本机已有的 {skipped} 条。'
            self.backend.messageRequested.emit('info','云端导入',self.status+' 本机修改不会被覆盖。')
        return self.job(call,done)

    def cloud_record_action(self,id,version,restore=False):
        if not self.logged_in() or not re.fullmatch('[a-f0-9-]{36}',str(id)):return
        def call():
            self.client.request('/api/cloud/items/'+id+('/restore' if restore else ''),{'version':version},'POST' if restore else 'DELETE')
            return self.client.list_records(getattr(self,'cloud_trash',False))
        def done(rows):
            self.cloud_library=rows;self.status='已恢复云端记录' if restore else '已移到云端回收站，本地记录保留'
            QTimer.singleShot(0,self.refresh)
        self.job(call,done)
