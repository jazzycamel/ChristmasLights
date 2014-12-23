#!/usr/bin/python
###############################################################################
#                                                                             #
# ChristmasLights                                                             #
# ==========                                                                  #
# WS2812 RGB LED based Christmas Lights controlled directly from a            #
#     Raspberry Pi with a web interface                                       #
# Copyright (C) 2014 Rob Kent                                                 #
#                                                                             #
# This program is free software: you can redistribute it and/or modify        #
# it under the terms of the GNU General Public License as published by        #
# the Free Software Foundation, either version 3 of the License, or           #
# (at your option) any later version.                                         #
#                                                                             #
# This program is distributed in the hope that it will be useful,             #
# but WITHOUT ANY WARRANTY; without even the implied warranty of              #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the               #
# GNU General Public License for more details.                                #
#                                                                             #
# You should have received a copy of the GNU General Public License           #
# along with this program.  If not, see <http://www.gnu.org/licenses/>.       #
#                                                                             #
###############################################################################

import sip
sip.setapi('QString',2)
sip.setapi('QVariant',2)

from PyQt4.QtCore import *
from PyQt4.QtNetwork import *
import os

from parser import HttpParser
from util import status_reasons

from NeoPixel import NeoPixel
from NeoPixel import Color_t_vector as ColorScheme
from NeoPixel import Color as _Color

class Color(_Color):
    def __init__(self, r=0, g=0, b=0):
        super(Color, self).__init__()
        self.r=r
        self.g=g
        self.b=b

rgb=ColorScheme()
rgb.extend([
    Color(255,0,0), Color(0,255,0), Color(0,0,255)
])

christmas=ColorScheme()
christmas.extend([
    Color(255,0,0), Color(0,255,0)
])

hanukkah=ColorScheme()
hanukkah.extend([
    Color(0,0,255), Color(255,255,255)
])

kwanzaa=ColorScheme()
kwanzaa.extend([
    Color(255,0,0), Color(0,0,0), Color(0,255,0)
])

rainbow=ColorScheme()
rainbow.extend([
    Color(255, 0, 0), Color(255, 128, 0), Color(255, 255, 0), Color(0, 255, 0), 
    Color(0, 0, 255), Color(128, 0, 255), Color(255, 0, 255)
])

incandescent=ColorScheme()
incandescent.extend([
    Color(255,140,20), Color(0,0,0)
])

fire=ColorScheme()
fire.extend([
    Color(255, 0, 0), Color(255, 102, 0), Color(255, 192, 0)
])

schemes=[incandescent, rgb, christmas, hanukkah, kwanzaa, rainbow, fire]

BARS=0
GRADIENT=1

barWidthValues=[1,3,6]
gradientWidthValues=[12,6,2]
speedValues=[0,500,250,50]

ext2ct={
    'html' : 'text/html; charset="utf8"',
    'css'  : 'text/css',
    'js'   : 'application/javascript',
    'png'  : 'image/png',
    'jpg'  : 'image/jpeg',
    'gif'  : 'image/gif',
    'json' : 'application/json',
}

RESPONSE  = 'HTTP/1.0 {code} {status}\r\n'
RESPONSE += 'Server: HttpServer\r\n'
RESPONSE += 'Connection: close\r\n'
RESPONSE += 'Content-Type: {content-type}\r\n'
RESPONSE += '\r\n'
RESPONSE += '{content}'
RESPONSE += '\n'

class Error404(Exception): pass

class HttpServer(QTcpServer):
    schemeChanged=pyqtSignal(int)
    patternChanged=pyqtSignal(int)
    widthChanged=pyqtSignal(int)
    speedChanged=pyqtSignal(int)
    stopThread=pyqtSignal()

    def __init__(self, parent=None, **kwargs):
        QTcpServer.__init__(self, parent, **kwargs)

        self._worker=None
        self._thread=None
        self._sockets=[]

    def incomingConnection(self, handle):
        if not self.isListening(): return

        s=QTcpSocket(self, readyRead=self.readClient, disconnected=self.discardClient)
        s.setSocketDescriptor(handle)
        self._sockets.append(s)

    def start(self, host=QHostAddress.LocalHost, port=8080, root='.'):
        self._root=root

        self._thread=QThread(finished=self._stop)
        self._worker=Worker(finished=self._thread.quit)

        self.schemeChanged.connect(self._worker.setScheme)
        self.patternChanged.connect(self._worker.setPattern)
        self.widthChanged.connect(self._worker.setWidth)
        self.speedChanged.connect(self._worker.setSpeed)
        self.stopThread.connect(self._worker.stop)

        self._thread.started.connect(self._worker.work)
        self._worker.moveToThread(self._thread)
        self._thread.start()

        return self.listen(QHostAddress(host),port)

    def _stop(self):
        if self.isListening(): self.close()
        QCoreApplication.instance().quit()

    def stop(self, stop): self.stopThread.emit()

    def readClient(self):
        s=self.sender()
        headers=str(s.readAll())

        p=HttpParser()
        plen=p.execute(headers, len(headers))

        if p.get_method()=="GET":
            path=p.get_path()

            try:
                if path.startswith("/ajax"):
                    code=200
                    ext='json'
                    content=""

                    method,arg=path.split('/')[2:]
                    getattr(self, method)(int(arg))

                else:
                    try:
                        _path=os.path.join(self._root, path[1:])
                        if not os.path.exists(_path): raise Error404
                        elif os.path.isdir(_path):
                            _path=os.path.join(_path, 'index.html')
                            if not os.path.exists(_path): raise Error404

                        ext=os.path.splitext(_path)[1][1:].lower()
                        code=200
                        with open(_path, 'rb') as f: content=f.read()

                    except Error404 as e:
                        code=404
                        ext='html'
                        content='<h1>404 - File Not Found ({0})</h1>'.format(path)

            except Exception as e:
                code=500
                ext='html'
                content='<h1>500 - Internal Error</h1>'

                print e

            _resp={
                'code'         : code,
                'status'       : status_reasons[code],
                'content-type' : ext2ct[ext],
                'content'      : content
            }
            response=RESPONSE.format(**_resp)

        elif p.get_method()=='POST':
            print "POST", headers
            response=''

        else: response=''
        
        s.writeData(response)
        s.waitForBytesWritten()
        s.close()

    def discardClient(self):
        s=self.sender()
        self._sockets.remove(s)
        s.deleteLater()

    def scheme(self, scheme): self.schemeChanged.emit(scheme)

    def pattern(self, pattern): self.patternChanged.emit(pattern)

    def width(self, width): self.widthChanged.emit(width)

    def speed(self, speed): self.speedChanged.emit(speed)

from time import sleep

class Worker(QObject):
    finished=pyqtSignal()

    def __init__(self, parent=None, **kwargs):
        super (Worker, self).__init__(parent, **kwargs)

        self._stop=False
        self._scheme=0
        self._pattern=0
        self._width=0
        self._speed=0

	self._neoPixel=NeoPixel(24)
        self._neoPixel.setBrightness(.4)

    @pyqtSlot()
    def work(self):
        if self._stop:
            self._neoPixel.clear()
            self._neoPixel.show()
            self.finished.emit()
            return    

        scheme=schemes[self._scheme]
        speed=speedValues[self._speed]

        if self._pattern==BARS:
            self._neoPixel.bars(scheme, barWidthValues[self._width], speed)        
        elif self._pattern==GRADIENT:
            self._neoPixel.gradient(scheme, gradientWidthValues[self._width], speed)

        QTimer.singleShot(10, self.work)

    @pyqtSlot(int)
    def setScheme(self, scheme): self._scheme=scheme

    @pyqtSlot(int)
    def setPattern(self, pattern): self._pattern=pattern

    @pyqtSlot(int)
    def setWidth(self, width): self._width=width

    @pyqtSlot(int)
    def setSpeed(self, speed): self._speed=speed

    @pyqtSlot()
    def stop(self): self._stop=True

if __name__=="__main__":
    from sys import argv, exit

    a=QCoreApplication(argv)
    h=HttpServer()
    if not  h.start(
        "192.168.0.13",
        80,
        QDir('./www').absolutePath()
    ):
        print 'Fail!'
        exit(1)
    print "Ok"
    exit(a.exec_())
