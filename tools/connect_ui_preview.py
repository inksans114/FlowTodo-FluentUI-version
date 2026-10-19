import os,sys
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['QTWEBENGINE_CHROMIUM_FLAGS']='--disable-gpu --disable-gpu-compositing'
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QTimer,QUrl
app=QApplication([]);view=QWebEngineView();view.resize(1280,900);view.show()
view.load(QUrl('http://127.0.0.1:4199/connect?code=ABCDEF1234'))
def shot():
 p=Path(__file__).resolve().parents[1]/'work/cloud-preview/connect-page.png';view.grab().save(str(p));print('Connect preview rendered',flush=True);app.quit()
QTimer.singleShot(6000,shot);app.exec()
