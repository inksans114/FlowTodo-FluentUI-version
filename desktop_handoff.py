"""Public wake-up links only; the pending secret remains in the OS-protected vault."""
import hashlib,subprocess,sys
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from PySide6.QtCore import QObject,Signal,QIODevice,QTimer
from PySide6.QtNetwork import QLocalServer,QLocalSocket

def wake_code(value):
    import re
    if not isinstance(value,str) or len(value)>160:return None
    try:
        u=urlsplit(value);q=parse_qs(u.query,strict_parsing=True)
        if (u.scheme,u.netloc,u.path)!=('flowtodo','auth','/complete') or u.fragment or set(q)!={'code'} or len(q['code'])!=1:return None
        code=q['code'][0]
        return code if re.fullmatch('[A-F0-9]{10}',code) else None
    except ValueError:return None

def register_protocol(compiled=None):
    if sys.platform!='win32':return
    from app_paths import windows_package_family
    if windows_package_family():return  # MSIX registers the protocol in its manifest.
    import winreg
    from startup_manager import resolve_launch
    launch=resolve_launch(Path(__file__).parent,compiled=compiled)
    quoted=launch.command+' "%1"'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Classes\flowtodo') as key:
        winreg.SetValueEx(key,'',0,winreg.REG_SZ,'URL:FlowTodo account handoff')
        winreg.SetValueEx(key,'URL Protocol',0,winreg.REG_SZ,'')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Classes\flowtodo\shell\open\command') as key:winreg.SetValueEx(key,'',0,winreg.REG_SZ,quoted)

class Handoff(QObject):
    wake=Signal(str)
    def __init__(self,directory,parent=None):
        super().__init__(parent);self.name='FlowTodo-auth-'+hashlib.sha256(str(Path(directory).resolve()).encode()).hexdigest()[:24]
        self.server=QLocalServer(self);self.server.setSocketOptions(QLocalServer.UserAccessOption)
        self.server.newConnection.connect(self.receive);self.buffers={}
    def forward(self,code):
        socket=QLocalSocket();socket.connectToServer(self.name,QIODevice.ReadWrite)
        if not socket.waitForConnected(700):return False
        socket.write((code+'\n').encode())
        if socket.bytesToWrite()>0 and not socket.waitForBytesWritten(700):return False
        if not socket.bytesAvailable():socket.waitForReadyRead(1000)
        accepted=bytes(socket.readAll())==b'OK\n';socket.disconnectFromServer();return accepted
    def listen(self):return self.server.listen(self.name)
    def receive(self):
        while self.server.hasPendingConnections():
            socket=self.server.nextPendingConnection();self.buffers[socket]=bytearray()
            socket.readyRead.connect(lambda s=socket:self.read(s))
            socket.disconnected.connect(lambda s=socket:self.drop(s));self.read(socket)
    def drop(self,socket):
        self.buffers.pop(socket,None)
        from shiboken6 import isValid
        if isValid(socket):socket.deleteLater()
    def read(self,socket):
        data=self.buffers.get(socket)
        if data is None:return
        data.extend(bytes(socket.readAll()))
        if len(data)>32:socket.abort();return
        if b'\n' in data:
            try:code=data.decode('ascii').strip()
            except UnicodeError:socket.abort();return
            import re
            if re.fullmatch('[A-F0-9]{10}',code):
                self.wake.emit(code);socket.write(b'OK\n');socket.flush()
                # The caller closes only after reading the acknowledgement.
                from shiboken6 import isValid
                QTimer.singleShot(2000,lambda s=socket:s.disconnectFromServer() if isValid(s) else None)
                return
            socket.disconnectFromServer()
