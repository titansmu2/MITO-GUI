#ICT Mumbai Version V_22.704.020
import sys
import time
import serial
import picamera
import os
import shutil
import psutil
from os.path import isfile,join
from datetime import datetime
from pathlib import Path
from cryptography.fernet import Fernet

from PIL import Image
import RPi.GPIO as gpio
try:
    import Queue
except:
    import queue as Queue
from PySide import QtGui
from PySide import QtCore
from PySide.QtCore import QTimer
from PySide.QtGui import *
from PySide.QtCore import *
from os import listdir
from os import path

app = QApplication(sys.argv)

class SerialThreadMKS(QtCore.QThread):
    def __init__(self, portname, baudrate): # Initialise with serial port details
        QtCore.QThread.__init__(self)
        self.portname, self.baudrate = portname, baudrate
        self.txq = []
        self.running = True
        self.acknowledged = 0;
        self.buffer = 1;
        self.extruderType = 1
        self.zPos = 0
        self.avDiff = 0
        self.needleSensing = "NONE"
        self.aStartX = 60
        self.aStartY = 110
        self.aStartZ = 35
        self.vStartX = 15
        self.vStartY = 110
        self.vStartZ = 35
        self.atriumServoPos = 0
        self.ventricleServoPos = 100

        self.cameraNeeded = False
        self.showCamera = True
        self.firstTime = True
        self.firstTimePreview = False
        self.gcodeName = "-"
        self.recording = False
        self.directory = "-"
        
    # Convert bytes to string
    def bytesToStr(self,d):
        return d if type(d) is str else "".join([chr(b) for b in d])

    def serialOut(self, s):                   # Write outgoing data to serial port if open
        self.txq.append(s)                     # ..using a queue to sync with reader thread
        #print("M in " + s)

    def run(self):                          # Run serial reader thread
        print("Opening MKS %s at %u baud" % (self.portname, self.baudrate))
        try:
                
            f1 = open('/home/pi/Tvasta/TouchScreen/PrinterSettings.txt', "r")
            self.time = datetime.now()
            for l in f1:
                w = l.split()
                if(w[0] == "ATRIUMX"):
                    self.aStartX = float(w[1])
                if(w[0] == "ATRIUMY"):
                    self.aStartY = float(w[1])
                if(w[0] == "ATRIUMZ"):
                    self.aStartZ = float(w[1])
                if(w[0] == "VENTRICLEX"):
                    self.vStartX = float(w[1])
                if(w[0] == "VENTRICLEY"):
                    self.vStartY = float(w[1])
                if(w[0] == "VENTRICLEZ"):
                    self.vStartZ = float(w[1])
                if(w[0] == "ATRIUMSERVO"):
                    self.atriumServoPos = float(w[1])
                if(w[0] == "VENTRICLESERVO"):
                    self.ventricleServoPos = float(w[1])
            f1.close()
            self.serialMKS = serial.Serial(self.portname, self.baudrate,
                                           timeout=0.1)
            time.sleep(0.2)
            self.serialMKS.flushInput()
            #self.txq.append("M42 P63 S0\n");
            #self.txq.append("M42 P59 S0\n");       
        except:
            self.serialMKS = None    
        if not self.serialMKS:
            print("Can't open port")
            self.running = False
        
        with picamera.PiCamera() as camera:
            camera.resolution = (1200, 500)
            camera.framerate = 30
        while self.running:
                        
            if(self.needleSensing  != "NONE"):
                if(gpio.input(18) == True and self.txq != [] and  "G28" not in self.txq[0]):
                    print("yatah")
                    time.sleep(1)
                    self.txq = []
                    #print(self.needleSensing)
                    if("ATRIUM_ROUGHD" in self.needleSensing):
                        self.needleSensing = "ATRIUM_FINE" 
                        self.aStartZ = self.aStartZ +3 
                        self.txq.append("G1 Z" + str(self.aStartZ) + ";\n")
                        self.txq.append("M400;\n")
                    elif("ATRIUM_FINED" in self.needleSensing):
                        self.needleSensing = "READYA"
                        #print(round(self.aStartZ,1))
                    elif("VENTRICLE_ROUGHD" in self.needleSensing):
                        self.needleSensing = "VENTRICLE_FINE" 
                        self.vStartZ = self.vStartZ +3
                        self.txq.append("G1 Z" + str(self.vStartZ) + ";\n")
                        self.txq.append("M400;\n")
                    elif("VENTRICLE_FINED" in self.needleSensing):
                        self.needleSensing = "READYV"
                        #print(round(self.vStartZ,1))
            
                elif len(self.txq) == 0:
                    if("ATRIUM" in self.needleSensing):
                        if("ROUGH" in self.needleSensing):
                            #print(len(self.txq))
                            self.txq.append("G1 X" + str(self.aStartX + self.aMoveBy) +" Y" + str(self.aStartY)  + " Z" + str(self.aStartZ - 1) + " F600;\n")
                            self.txq.append("M400;\n")
                            self.aStartZ = self.aStartZ - 1
                            self.aMoveBy = -self.aMoveBy
                            self.needleSensing = "ATRIUM_ROUGHD"
                        elif("FINE" in self.needleSensing):
                            self.needleSensing = "ATRIUM_FINED"
                            self.txq.append("G1 X" + str(self.aStartX + self.aMoveBy) +" Y" + str(self.aStartY)  + " Z" + str(self.aStartZ - 0.1) + " F600;\n")
                            self.txq.append("M400;\n")
                            self.aStartZ = self.aStartZ - 0.1
                            self.aMoveBy = -self.aMoveBy
                        elif("HOME" in self.needleSensing):
                            self.txq.append("G28 Z0;\n")
                            self.txq.append("G28 Y0;\n")
                            self.txq.append("G28 X0;\n")
                            self.txq.append("M280 P0 S" + str(self.atriumServoPos) + "\n");
                            #self.aStartX = 54
                            #self.aStartY = 110
                            self.aStartZ = 35
                            self.aMoveBy = 2
                            self.txq.append("G1 X" + str(self.aStartX) +" Y" + str(self.aStartY)  + " Z" + str(self.aStartZ) + " F600;\n")
                            self.txq.append("M400;\n")
                            self.needleSensing = "ATRIUM_ROUGH"
                    if("VENTRICLE" in self.needleSensing):
                        if("ROUGH" in self.needleSensing):
                            #print(len(self.txq))
                            self.txq.append("G1 X" + str(self.vStartX + self.vMoveBy) +" Y" + str(self.vStartY)  + " Z" + str(self.vStartZ - 1) + " F600;\n")
                            self.txq.append("M400;\n")
                            self.vStartZ = self.vStartZ - 1
                            self.vMoveBy = -self.vMoveBy
                            self.needleSensing = "VENTRICLE_ROUGHD"
                        elif("FINE" in self.needleSensing):
                            self.needleSensing = "VENTRICLE_FINED"
                            self.txq.append("G1 X" + str(self.vStartX + self.vMoveBy) +" Y" + str(self.vStartY)  + " Z" + str(self.vStartZ - 0.1) + " F600;\n")
                            self.txq.append("M400;\n")
                            self.vStartZ = self.vStartZ - 0.1
                            self.vMoveBy = -self.vMoveBy
                        elif("HOME" in self.needleSensing):
                            self.txq.append("G28 Z0;\n")
                            self.txq.append("G28 Y0;\n")
                            self.txq.append("G28 X0;\n")
                            self.txq.append("M280 P0 S" + str(self.ventricleServoPos) + "\n");
                            #self.vStartX = 4
                            #self.vStartY = 110
                            self.vStartZ = 35
                            self.vMoveBy = 2
                            self.txq.append("G1 X" + str(self.vStartX) +" Y" + str(self.vStartY)  + " Z" + str(self.vStartZ) + " F600;\n")
                            self.txq.append("M400;\n")
                            self.needleSensing = "VENTRICLE_ROUGH"
             
            if self.serialMKS.in_waiting > 0:
                self.time = datetime.now()
                s = self.bytesToStr(self.serialMKS.readline()).rstrip()
                #print(s)
                if "ok" in s:
                    self.acknowledged = self.acknowledged - 1
                    #print(self.acknowledged)
                    #outCommand = self.txq.pop(0)
            elif self.acknowledged <= 0 and len(self.txq) != 0:
                #print(self.acknowledged)
                txd = str(self.txq[0])               # If Tx data in queue, write to serial port
                self.txq.pop(0)
                if("Extruder1" in txd) and self.extruderType == 2:
                    self.extruderType = 1
                    txd = "G92 Z" + str(round(float(w[1:]) + self.avDiff,2)) + ";\n"
                elif("Extruder2" in txd)  and self.extruderType == 1:
                    self.extruderType = 2
                    txd = "G92 Z" + str(round(float(w[1:]) - self.avDiff,2)) + ";\n"
                elif("Z" in txd and "G0" in txd ):
                    words = txd.split(" ")
                    for w in words:
                        if("Z" in w):
                            self.zPos = round(float(w[1:]),2)
                            #print("Zpos")
                            #print(self.zPos)
                            break
                print("GCODE " + txd)
                self.acknowledged = self.acknowledged +1
                #print(self.acknowledged)
                self.serialMKS.write(txd.encode())   
        
            if (self.cameraNeeded == True and self.firstTime == True):
                self.firstTime = False
                camera.start_preview()
                if(self.recording == True):
                    camera.start_recording(self.directory + "/recording.h264")
                # Load the arbitrarily sized image
                img1 = Image.open('/home/pi/Tvasta/TouchScreen/Images/stopSmall.png')
                img2 = Image.open('/home/pi/Tvasta/TouchScreen/Images/pauseSmall.png')
                img3 = Image.open('/home/pi/Tvasta/TouchScreen/Images/cameraSmall.png')
                # Create an image padded to the required size with
                # mode 'RGB'
                #pad = Image.new('RGBA', 
                #        (((img.size[0]) // 32) * 32,((img.size[1]) // 2) * 16,))
                
                pad = Image.new('RGBA', size = (1024,512))
                # Paste the original image into the padded one
                pad.paste(img3, (5,310))
                pad.paste(img2, (415,310))
                pad.paste(img1, (825,310))
                
                # Add the overlay with the padded image as the source,
                # but the original image's dimensions
                o = camera.add_overlay(pad.tobytes(), size=pad.size)
                # By default, the overlay is in layer 0, beneath the
                # preview (which defaults to layer 2). Here we make
                # the new overlay semi-transparent, then move it above
                # the preview
                o.alpha = 255
                o.layer = 3
                print("Overlay Created Start")
            if(self.cameraNeeded == False and self.firstTime == False):
                camera.stop_preview()
                if(self.recording == True):
                    camera.stop_recording()
                camera.remove_overlay(o)
                self.firstTime = True
                print("Overlay removed Start")
        
            if(self.showCamera == True  and self.firstTimePreview == True):
                self.firstTimePreview = False
                img1 = Image.open('/home/pi/Tvasta/TouchScreen/Images/stopSmall.png')
                img2 = Image.open('/home/pi/Tvasta/TouchScreen/Images/pauseSmall.png')
                img3 = Image.open('/home/pi/Tvasta/TouchScreen/Images/cameraSmall.png')
                pad = Image.new('RGBA', size = (1024,512))
                pad.paste(img3, (5,310))
                pad.paste(img2, (415,310))
                pad.paste(img1, (825,310))
                o = camera.add_overlay(pad.tobytes(), size=pad.size)
                o.alpha = 255
                o.layer = 3
                camera.start_preview()
                print("Overlay started Show")
            elif(self.showCamera == False and self.firstTimePreview == True):
                self.firstTimePreview = False
                camera.stop_preview()
                camera.remove_overlay(o)
                print("Overlay removed show")
        if self.serialMKS:                                    # Close serial port when thread finished
            self.serialMKS.close()
            self.serialMKS = None

                          
class OriginTouchScreen(QWidget):
    def __init__(self):
        #Inititalisation Of Window
        super(OriginTouchScreen, self).__init__()
        self.setWindowFlags(
        QtCore.Qt.Window |
        QtCore.Qt.FramelessWindowHint
        )
        self.setStyleSheet("background : #FFFFFF")
        self.showFullScreen()

        #Establish Serial Communication to boards
        self.serialThreadMKS = SerialThreadMKS("/dev/ttyUSB0", 250000)   # Start serial thread
                                      
            
        self.serialThreadMKS.start()
        
                
        gpio.setmode(gpio.BCM)
        gpio.setup(18, gpio.IN)
        
        #self.needleDetectionThread = NeedleDetectionThread()   # Start thread
        #self.needleDetectionThread.start()
        


        #Define Global Variables
        self.DefineGlobalVariables()

        #Create Custom Fonts
        self.CreateCustomFonts()

        #Create a Timer to Update Values
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda:self.TimerTick())
        self.timer.start(1000)
        self.val = 0
        
        #Progress Bar to detect % of print
        self.pbar = QProgressBar(self)
        self.pbar.setGeometry(0,0,1200,0)
        self.pbar.setStyleSheet("QProgressBar{ border: 4px solid #339A99; border-radius: 5px; text-align: center;} QProgressBar::chunk { background-color: #339A99; }")
        self.totalGcodeLine = 1
        self.printStarted = False

        #Create Every Page
        self.CreateMainPage()
        self.CreateManualControlPage()
        self.CreateMotionPage()
        self.CreateCalibrationPage()
        self.CreateEditXOffsetPage()
        self.CreateEditYOffsetPage()
        self.CreateEditZ1OffsetPage()
        self.CreateEditZ2OffsetPage()
        self.CreateUVPage()
        self.CreatePrintPage()
        self.CreatePrintMonitorPage()
        self.CreatePrintFinishPage()
        self.CreateDataInfoPage()
        self.CreateDataPage()
        self.CreateDataRetrievePage()
        self.CreateLoadFilePage()

        #Create Stack to place all created Pages
        self.CreateStackedWidget()

        #Show the application
        hbox = QHBoxLayout(self)
        
        hbox.addWidget(self.stack)
        self.layout().setContentsMargins(0,0,50,0)
        self.setLayout(hbox)
        self.setWindowTitle('Tvasta BioPrinter')
        self.setCursor(Qt.BlankCursor)
        self.show()

    def CreateStackedWidget(self):
        self.stack = QStackedWidget (self)
        self.stack.addWidget (self.MainPage)
        self.stack.addWidget (self.ManualControlPage)
        self.stack.addWidget (self.MotionPage)
        self.stack.addWidget (self.CalibrationPage)
        self.stack.addWidget (self.EditXOffsetPage)
        self.stack.addWidget (self.EditYOffsetPage)
        self.stack.addWidget (self.EditZ1OffsetPage)
        self.stack.addWidget (self.EditZ2OffsetPage)
        self.stack.addWidget (self.UVPage)
        self.stack.addWidget (self.PrintPage)
        self.stack.addWidget (self.PrintMonitorPage)
        self.stack.addWidget (self.PrintFinishPage)
        self.stack.addWidget (self.DataInfoPage)
        self.stack.addWidget (self.DataPage)
        self.stack.addWidget (self.DataRetrievePage)
        self.stack.addWidget (self.LoadFilePage)


    def DefineGlobalVariables(self):
        #GPIO stuff
        self.SENSOR = 18
        gpio.setmode(gpio.BCM)
        gpio.setup(self.SENSOR, gpio.IN)

        self.txq=[]
        self.printPaused = False

        #Store XYZ Coordinates
        self.xPos = 0.0
        self.yPos = 0.0
        self.zPos = 0.0
        
        #Store XYZ Home Location Coordinates
        self.xHomePosition = 0.0
        self.yHomePosition = 130.0
        self.zHomePosition = 65.0
        
        
        #Store XYZ Offset Values
        self.xOffset = 0.0
        self.yOffset = 0.0
        self.z1Offset = 0.0
        self.z2Offset = 0.0
        
        #Needle height values
        self.atriumHeight = 0.0
        self.ventricleHeight = 0.0
        self.needleSensorToBed = 12.3
        self.decryptionKey = "hsziT3bnsxzacuhOZ9HJC_9guDCIOJF0Gy7p05y7FHs="
        self.TouchScreenFileName = "OriginGUI.py"
        
        self.disk = psutil.disk_usage('/');
        self.diskFree = 100 - self.disk.percent
        
        
        #print(str(self.diskFree))
                
        f = open('/home/pi/Tvasta/TouchScreen/settings.txt', "r")
        for l in f:
            w = l.split()
            if(w[0] == "Z1offset"):
                self.z1Offset = float(w[1])
            if(w[0] == "Z2offset"):
                self.z2Offset = float(w[1])
            if(w[0] == "Xoffset"):
                self.xOffset = float(w[1])
            if(w[0] == "Yoffset"):
                self.yOffset = float(w[1])
            if(w[0] == "AtriumHeight"):
                self.atriumHeight = float(w[1])
            if(w[0] == "VentricleHeight"):
                self.ventricleHeight = float(w[1])
            if(w[0] == "DecryptionKey"):
                self.decryptionKey = float(w[1])
                 
        
        f.close()   
        
        f1 = open('/home/pi/Tvasta/TouchScreen/PrinterSettings.txt', "r")
        for l in f1:
            w = l.split()
            if(w[0] == "HOMEPOSITIONX"):
                self.xHomePosition = float(w[1])
            elif(w[0] == "HOMEPOSITIONY"):
                self.yHomePosition = float(w[1])
            elif(w[0] == "HOMEPOSITIONZ"):
                self.zHomePosition = float(w[1])
            elif(w[0] == "DECRYPTIONKEY"):
                self.decryptionKey = w[1]
            elif(w[0] == "BEDTOSENSOR"):
                self.needleSensorToBed = float(w[1])
            elif(w[0] == "TOUCHSCREENFILENAME"):
                self.TouchScreenFileName = w[1]
            elif(w[0] == "CENTERX"):
                self.centerX = float(w[1])
            elif(w[0] == "CENTERY"):
                self.centerY = float(w[1])
            elif(w[0] == "CENTERZ"):
                self.centerZ = float(w[1])
            elif(w[0] == "EXTRUDEROFFSETX"):
                self.extruderOffsetX = float(w[1])
            elif(w[0] == "EXTRUDEROFFSETY"):
                self.extruderOffsetY = float(w[1])
            elif(w[0] == "EXTRUDEROFFSETZ"):
                self.extruderOffsetZ = float(w[1])
        f1.close()
        
        self.dataLog = False
        self.gCodeFile = "-";
        self.speed = "-"
        self.time = "-"
        self.uv = "-"
        self.material = "-"
        self.needle = "-"
        self.pressure = "-"
        self.layerNo = 0
        self.layerHeight = 0.2
        
        self.nameValue = QLabel("-")
        self.speedValue = QLabel("-")
        self.timeValue = QLabel("-")
        
        self.printNameValue = QLabel("-")
        self.printSpeedValue = QLabel("-")
        self.printTimeValue = QLabel("-")
        self.printUVLabel = QLabel("-")
        self.printMaterialLabel = QLabel("-")
        self.printNeedleLabel = QLabel("-")
        self.printPressureLabel = QLabel("-")
        
        self.ratingFrame = QtGui.QFrame()
        self.calibrationFrame = QtGui.QFrame()
        
        self.logData  = False


    def CreateCustomFonts(self):
        self.PicLabelFont = QtGui.QFont()
        self.PicLabelFont.setBold(True)
        self.PicLabelFont.setWeight(100)
        self.PicLabelFont.setFamily("Ubuntu Mono")
        self.PicLabelFont.setPointSize(15)

        self.SmallLabelFont = QtGui.QFont()
        self.SmallLabelFont.setBold(True)
        self.SmallLabelFont.setWeight(100)
        self.SmallLabelFont.setFamily("Ubuntu Mono")
        self.SmallLabelFont.setPointSize(10)

        self.MediumLabelFont = QtGui.QFont()
        self.MediumLabelFont.setBold(True)
        self.MediumLabelFont.setWeight(100)
        self.MediumLabelFont.setFamily("Ubuntu Mono")
        self.MediumLabelFont.setPointSize(25)

        self.BigLabelFont = QtGui.QFont()
        self.BigLabelFont.setBold(True)
        self.BigLabelFont.setWeight(100)
        self.BigLabelFont.setFamily("Ubuntu Mono")
        self.BigLabelFont.setPointSize(40)
        
        self.HugeLabelFont = QtGui.QFont()
        self.HugeLabelFont.setBold(True)
        self.HugeLabelFont.setWeight(100)
        self.HugeLabelFont.setFamily("Ubuntu Mono")
        self.HugeLabelFont.setPointSize(60)


    def CreateMainPage(self):
        grid = QGridLayout()
        b1 = QPushButton()
        b1.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/load.png")))
        b1.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 20;} ")
        b1.setFixedSize(QSize(200,200))
        b1.setIconSize(QSize(200,200))
        b1.setProperty("ID",0)
        b1.setProperty("NAME","Load")
        b1.setProperty("TO",9)
        b1.clicked.connect(lambda:self.GoToPage(b1))
        b1Label = QLabel(b1.property("NAME"))
        b1Label.setFont(self.PicLabelFont)

        b2 = QPushButton()
        b2.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/printOptions.png")))
        b2.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 20;} ")
        b2.setFixedSize(QSize(200,200))
        b2.setIconSize(QSize(200,200))
        b2.setProperty("ID",0)
        b2.setProperty("NAME","MCU")
        b2.setProperty("TO",1)
        b2.clicked.connect(lambda:self.GoToPage(b2))
        b2Label = QLabel(b2.property("NAME"))
        b2Label.setFont(self.PicLabelFont)

        b3 = QPushButton()
        b3.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/InfoData.png")))
        b3.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 20;} ")
        b3.setFixedSize(QSize(200,200))
        b3.setIconSize(QSize(200,200))
        b3.setProperty("ID",0)
        b3.setProperty("NAME","Data & Info")
        b3.setProperty("TO",12)
        b3.clicked.connect(lambda:self.GoToPage(b3))
        b3Label = QLabel(b3.property("NAME"))
        b3Label.setFont(self.PicLabelFont)

        grid.addWidget(b1,0,0)
        grid.addWidget(b2,0,1)
        grid.addWidget(b3,0,2)
        grid.addWidget(b1Label,1,0, Qt.AlignCenter)
        grid.addWidget(b2Label,1,1, Qt.AlignCenter)
        grid.addWidget(b3Label,1,2, Qt.AlignCenter)

        bottomHBox = QtGui.QHBoxLayout()
        pixmap = QtGui.QPixmap()
        pixmap.load("/home/pi/Tvasta/TouchScreen/Images/avaylogo.png")
        pixmap = pixmap.scaledToWidth(190)
        back = QLabel()
        back.setPixmap(pixmap)
        back.setFixedSize(QSize(190,115))

        bottomHBox.addStretch()
        bottomHBox.addStretch()
        bottomHBox.addStretch()
        bottomHBox.addStretch()
        bottomHBox.addStretch()
        bottomHBox.addStretch()
        bottomHBox.addStretch()
        bottomHBox.addWidget(back)
        bottomHBox.addStretch()

        fullVBox = QtGui.QVBoxLayout()
        fullVBox.addStretch()
        fullVBox.addLayout(grid)
        fullVBox.addStretch()
        fullVBox.addLayout(bottomHBox)

        self.MainPage = QWidget()
        self.MainPage.setLayout(fullVBox)


    def CreateManualControlPage(self):
        grid = QGridLayout()
        b1 = QPushButton()
        b1.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/3d_axes.png")))
        b1.setFixedSize(QSize(200,200))
        b1.setIconSize(QSize(200,200))
        b1.setProperty("ID",1)
        b1.setProperty("NAME","Motion")
        b1.setProperty("TO",2)
        b1.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 20;} ")
        b1.clicked.connect(lambda:self.GoToPage(b1))
        b1Label = QLabel(b1.property("NAME"))
        b1Label.setFont(self.PicLabelFont)

        b2 = QPushButton()
        b2.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/Calibration.png")))
        b2.setFixedSize(QSize(200,200))
        b2.setIconSize(QSize(200,200))
        b2.setProperty("ID",1)
        b2.setProperty("NAME","Calibration")
        b2.setProperty("TO",3)
        b2.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 20;}")
        b2.clicked.connect(lambda:self.GoToPage(b2))
        b2Label = QLabel(b2.property("NAME"))
        b2Label.setFont(self.PicLabelFont)

        b3 = QPushButton()
        b3.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/UV.png")))
        b3.setFixedSize(QSize(200,200))
        b3.setIconSize(QSize(180,180))
        b3.setProperty("ID",1)
        b3.setProperty("NAME","UV")
        b3.setProperty("TO",8)
        b3.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 20;}")
        b3.clicked.connect(lambda:self.GoToPage(b3))
        b3Label = QLabel(b3.property("NAME"))
        b3Label.setFont(self.PicLabelFont)

        grid.addWidget(b1,0,0)
        grid.addWidget(b2,0,1)
        grid.addWidget(b3,0,2)
        grid.addWidget(b1Label,1,0, Qt.AlignCenter)
        grid.addWidget(b2Label,1,1, Qt.AlignCenter)
        grid.addWidget(b3Label,1,2, Qt.AlignCenter)


        bottomHBox = QtGui.QHBoxLayout()
        back = QPushButton()
        back.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/back.png")))
        back.setFixedSize(QSize(190,115))
        back.setIconSize(QSize(150,75))
        back.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px} ")
        back.setProperty("NAME","Back to Main Page")
        back.setProperty("TO",0)
        back.clicked.connect(lambda:self.GoToPage(back))
        bottomHBox.addStretch()
        bottomHBox.addWidget(back)

        fullVBox = QtGui.QVBoxLayout()
        fullVBox.addStretch()
        fullVBox.addStretch()
        fullVBox.addLayout(grid)
        fullVBox.addStretch()
        fullVBox.addLayout(bottomHBox)

        self.ManualControlPage = QWidget()
        self.ManualControlPage.setLayout(fullVBox)


    def CreateMotionPage(self):
        grid = QGridLayout()
        xyGrid = QGridLayout()
        zGrid = QGridLayout()
        extruderGrid = QGridLayout()
        homeGrid = QGridLayout()

        xUp = QPushButton()
        xUp.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/RightArrow.png")))
        xUp.setFixedSize(QSize(80,80))
        xUp.setIconSize(QSize(50,50))
        xUp.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 40px; border-style: solid;");
        xUp.setProperty("ID",2)
        xUp.setProperty("NAME","X Increase")
        xUp.setProperty("DIRECTION",1)
        xUp.pressed.connect(lambda:self.HighLightCircle(xUp))
        xUp.released.connect(lambda:self.UnHighLightCircle(xUp))
        xUp.clicked.connect(lambda:self.Translate(xUp))

        xDown = QPushButton()
        xDown.setStyleSheet("font-size: 60px;");
        xDown.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/LeftArrow.png")))
        xDown.setFixedSize(QSize(80,80))
        xDown.setIconSize(QSize(50,50))
        xDown.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 40px; border-style: solid;");
        xDown.setProperty("ID",2)
        xDown.setProperty("NAME","X Decrease")
        xDown.setProperty("DIRECTION",-1)
        xDown.pressed.connect(lambda:self.HighLightCircle(xDown))
        xDown.released.connect(lambda:self.UnHighLightCircle(xDown))
        xDown.clicked.connect(lambda:self.Translate(xDown))

        yUp = QPushButton()
        yUp.setStyleSheet("font-size: 60px;");
        yUp.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/UpArrow.png")))
        yUp.setFixedSize(QSize(80,80))
        yUp.setIconSize(QSize(50,50))
        yUp.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 40px; border-style: solid;");
        yUp.setProperty("ID",2)
        yUp.setProperty("NAME","Y Increase")
        yUp.setProperty("DIRECTION",1)
        yUp.pressed.connect(lambda:self.HighLightCircle(yUp))
        yUp.released.connect(lambda:self.UnHighLightCircle(yUp))
        yUp.clicked.connect(lambda:self.Translate(yUp))

        yDown = QPushButton()
        yDown.setStyleSheet("font-size: 60px;");
        yDown.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/DownArrow.png")))
        yDown.setFixedSize(QSize(80,80))
        yDown.setIconSize(QSize(50,50))
        yDown.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 40px; border-style: solid;");
        yDown.setProperty("ID",2)
        yDown.setProperty("NAME","Y Decrease")
        yDown.setProperty("DIRECTION",-1)
        yDown.pressed.connect(lambda:self.HighLightCircle(yDown))
        yDown.released.connect(lambda:self.UnHighLightCircle(yDown))
        yDown.clicked.connect(lambda:self.Translate(yDown))

        self.xyMoveBy = QPushButton("0.1")
        self.xyMoveBy.setStyleSheet("border: 8px solid #ED9D61; border-radius: 40px; border-style: solid; background: #AAAAAA");
        self.xyMoveBy.setFont(self.PicLabelFont)
        self.xyMoveBy.setFixedSize(QSize(80,80))
        self.xyMoveBy.setProperty("ID","XY")
        self.xyMoveBy.setProperty("ACTION",0)
        self.xyMoveBy.pressed.connect(lambda:self.HighLightNumber(self.xyMoveBy))
        self.xyMoveBy.released.connect(lambda:self.UnHighLightNumber(self.xyMoveBy))
        self.xyMoveBy.clicked.connect(lambda:self.MoveByChanged(self.xyMoveBy))

        xHome = QPushButton()
        xHome.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/home.png")))
        xHome.setFixedSize(QSize(80,80))
        xHome.setIconSize(QSize(50,50))
        xHome.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 40px; border-style: solid;");
        xHome.setProperty("NAME","Home X")
        xHome.pressed.connect(lambda:self.HighLightHome(xHome))
        xHome.released.connect(lambda:self.UnHighLightHome(xHome))
        xHome.clicked.connect(lambda:self.HomeCommand(xHome))
        xHomeLabel = QLabel(xHome.property("NAME"))
        xHomeLabel.setFont(self.PicLabelFont)
        xHomeVbox = QVBoxLayout()
        xHomeVbox.addWidget(xHome)
        xHomeVbox.addWidget(xHomeLabel)

        yHome = QPushButton()
        yHome.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/home.png")))
        yHome.setFixedSize(QSize(80,80))
        yHome.setIconSize(QSize(50,50))
        yHome.setStyleSheet("background: #AAAAAA;  border: 8px solid #339A99; border-radius: 40px; border-style: solid;");
        yHome.setProperty("NAME","Home Y")
        yHome.pressed.connect(lambda:self.HighLightHome(yHome))
        yHome.released.connect(lambda:self.UnHighLightHome(yHome))
        yHome.clicked.connect(lambda:self.HomeCommand(yHome))
        yHomeLabel = QLabel(yHome.property("NAME"))
        yHomeLabel.setFont(self.PicLabelFont)
        yHomeVbox = QVBoxLayout()
        yHomeVbox.addWidget(yHome)
        yHomeVbox.addWidget(yHomeLabel)

        zHome = QPushButton()
        zHome.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/home.png")))
        zHome.setFixedSize(QSize(80,80))
        zHome.setIconSize(QSize(50,50))
        zHome.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 40px; border-style: solid;");
        zHome.setProperty("NAME","Home Z")
        zHome.pressed.connect(lambda:self.HighLightHome(zHome))
        zHome.released.connect(lambda:self.UnHighLightHome(zHome))
        zHome.clicked.connect(lambda:self.HomeCommand(zHome))
        zHomeLabel = QLabel(zHome.property("NAME"))
        zHomeLabel.setFont(self.PicLabelFont)
        zHomeVbox = QVBoxLayout()
        zHomeVbox.addWidget(zHome)
        zHomeVbox.addWidget(zHomeLabel)
        
        allHome = QPushButton()
        allHome.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/home.png")))
        allHome.setFixedSize(QSize(80,80))
        allHome.setIconSize(QSize(50,50))
        allHome.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 40px; border-style: solid;");
        allHome.setProperty("NAME","Home All")
        allHome.pressed.connect(lambda:self.HighLightHome(allHome))
        allHome.released.connect(lambda:self.UnHighLightHome(allHome))
        allHome.clicked.connect(lambda:self.HomeCommand(allHome))
        allHomeLabel = QLabel(allHome.property("NAME"))
        allHomeLabel.setFont(self.PicLabelFont)
        allHomeVbox = QVBoxLayout()
        allHomeVbox.addWidget(allHome)
        allHomeVbox.addWidget(allHomeLabel)
        allHomeVbox.addStretch()

        xyGrid.addWidget(self.xyMoveBy,1,1,Qt.AlignCenter)
        xyGrid.addWidget(xUp,1,2)
        xyGrid.addWidget(xDown,1,0)
        xyGrid.addWidget(yUp,0,1)
        xyGrid.addWidget(yDown,2,1)
        #xyGrid.addLayout(xHomeVbox,3,0)
        #xyGrid.addLayout(yHomeVbox,3,4)

        homeGrid.addLayout(xHomeVbox,0,0)
        homeGrid.addLayout(yHomeVbox,1,0)
        homeGrid.addLayout(zHomeVbox,2,0)

        zUp = QPushButton()
        zUp.setStyleSheet("font-size: 60px;");
        zUp.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/UpArrow.png")))
        zUp.setFixedSize(QSize(80,80))
        zUp.setIconSize(QSize(50,50))
        zUp.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 40px; border-style: solid;");
        zUp.setProperty("ID",2)
        zUp.setProperty("NAME","Z Decreases")
        zUp.setProperty("DIRECTION",-1)
        zUp.pressed.connect(lambda:self.HighLightCircle(zUp))
        zUp.released.connect(lambda:self.UnHighLightCircle(zUp))
        zUp.clicked.connect(lambda:self.Translate(zUp))

        zDown = QPushButton()
        zDown.setStyleSheet("font-size: 60px;");
        zDown.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/DownArrow.png")))
        zDown.setFixedSize(QSize(80,80))
        zDown.setIconSize(QSize(50,50))
        zDown.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 40px; border-style: solid;");
        zDown.setProperty("ID",2)
        zDown.setProperty("NAME","Z Increases")
        zDown.setProperty("DIRECTION",1)
        zDown.pressed.connect(lambda:self.HighLightCircle(zDown))
        zDown.released.connect(lambda:self.UnHighLightCircle(zDown))
        zDown.clicked.connect(lambda:self.Translate(zDown))

        self.zMoveBy = QPushButton("0.01")
        self.zMoveBy.setStyleSheet(" border: 8px solid #ED9D61; border-radius: 40px; border-style: solid; background-color: #AAAAAA");
        self.zMoveBy.setFont(self.PicLabelFont)
        self.zMoveBy.setFixedSize(QSize(80,80))
        self.zMoveBy.setProperty("ID","Z")
        self.zMoveBy.setProperty("ACTION",0)
        self.zMoveBy.pressed.connect(lambda:self.HighLightNumber(self.zMoveBy))
        self.zMoveBy.released.connect(lambda:self.UnHighLightNumber(self.zMoveBy))
        self.zMoveBy.clicked.connect(lambda:self.MoveByChanged(self.zMoveBy))

        zGrid.addWidget(zUp,0,0, Qt.AlignCenter)
        zGrid.addWidget(self.zMoveBy,1,0, Qt.AlignCenter)
        zGrid.addWidget(zDown,2,0, Qt.AlignCenter)
        #z1Grid.addLayout(z1HomeVbox,3,0, Qt.AlignCenter)
        
        atrium = QPushButton("A")
        atrium.setFixedSize(QSize(80,80))
        atrium.setFont(self.MediumLabelFont)
        atrium.setStyleSheet("border: 8px solid #339A99; border-radius: 40px; border-style: solid; background : #AAAAAA");
        atrium.pressed.connect(lambda:self.ExtruderOn(atrium))
        atrium.released.connect(lambda:self.ExtruderOff(atrium))
        atrium.setProperty("NAME","ATRIUM")
        atriumLabel = QLabel("Atrium")
        atriumLabel.setFont(self.PicLabelFont)
        
        
        ventricle = QPushButton("V")
        ventricle.setFixedSize(QSize(80,80))
        ventricle.setFont(self.MediumLabelFont)
        ventricle.setStyleSheet("border: 8px solid #339A99; border-radius: 40px; border-style: solid; background : #AAAAAA; outline: none");
        ventricle.pressed.connect(lambda:self.ExtruderOn(ventricle))
        ventricle.released.connect(lambda:self.ExtruderOff(ventricle))
        ventricle.setProperty("NAME","VENTRICLE")
        ventricleLabel = QLabel("Ventricle")
        ventricleLabel.setFont(self.PicLabelFont)
        
        chooseExtruder = QPushButton("A V")
        chooseExtruder.setFixedSize(QSize(80,80))
        chooseExtruder.setFont(self.PicLabelFont)
        chooseExtruder.setStyleSheet("border: 8px solid #ED9D61; border-radius: 40px; border-style: solid; background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,stop: 0 #AAAAAA, stop: 0.49 #AAAAAA, stop: 0.51 #339A99, stop: 1.0 #339A99);");
        chooseExtruder.setProperty("NAME","ChooseExtruder")
        chooseExtruder.setProperty("STATE","ATRIUM")
        chooseExtruder.clicked.connect(lambda:self.ChooseExtruder(chooseExtruder))
        
        extruderGrid.addWidget(atriumLabel,0,0,Qt.AlignCenter)
        extruderGrid.addWidget(ventricleLabel,4,0,Qt.AlignCenter)
        extruderGrid.addWidget(atrium,1,0,Qt.AlignCenter)
        extruderGrid.addWidget(ventricle,3,0,Qt.AlignCenter)
        extruderGrid.addWidget(chooseExtruder,2,0,Qt.AlignCenter)

        xPosLabel = QLabel("X: ")
        xPosLabel.setFont(self.SmallLabelFont)
        xDimLabel = QLabel("mm")
        xDimLabel.setFont(self.SmallLabelFont)

        yPosLabel = QLabel("Y: ")
        yPosLabel.setFont(self.SmallLabelFont)
        yDimLabel = QLabel("mm")
        yDimLabel.setFont(self.SmallLabelFont)

        zPosLabel = QLabel("Z: ")
        zPosLabel.setFont(self.SmallLabelFont)
        zDimLabel = QLabel("mm")
        zDimLabel.setFont(self.SmallLabelFont)

        bottomHbox = QtGui.QHBoxLayout()
        back = QPushButton()
        back.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/back.png")))
        back.setFixedSize(QSize(190,115))
        back.setIconSize(QSize(150,75))
        back.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px} ")
        back.setProperty("NAME","Back to MCU")
        back.setProperty("TO",1)
        back.clicked.connect(lambda:self.GoToPage(back))

        self.xPosValue = QLabel()
        self.xPosValue.setText(str(self.xPos))
        self.xPosValue.setFont(self.PicLabelFont)
        self.xPosValue.setFixedSize(QSize(65, 50))
        self.yPosValue = QLabel()
        self.yPosValue.setText(str(self.yPos))
        self.yPosValue.setFont(self.PicLabelFont)
        self.yPosValue.setFixedSize(QSize(65, 50))
        self.zPosValue = QLabel()
        self.zPosValue.setText(str(self.zPos))
        self.zPosValue.setFont(self.PicLabelFont)
        self.zPosValue.setFixedSize(QSize(65, 50))

        bottomHbox.addLayout(allHomeVbox)
        bottomHbox.addStretch()
        bottomHbox.addWidget(xPosLabel)
        bottomHbox.addWidget(self.xPosValue)
        bottomHbox.addWidget(xDimLabel)
        bottomHbox.addStretch()
        bottomHbox.addWidget(yPosLabel)
        bottomHbox.addWidget(self.yPosValue)
        bottomHbox.addWidget(yDimLabel)
        bottomHbox.addStretch()
        bottomHbox.addWidget(zPosLabel)
        bottomHbox.addWidget(self.zPosValue)
        bottomHbox.addWidget(zDimLabel)
        bottomHbox.addWidget(back)

        topHBox = QtGui.QHBoxLayout()
        topHBox.addLayout(homeGrid)
        topHBox.addStretch()
        topHBox.addLayout(xyGrid)
        topHBox.addStretch()
        topHBox.addLayout(zGrid)
        topHBox.addStretch()
        topHBox.addLayout(extruderGrid)
        topHBox.addStretch()
        

        fullVBox = QtGui.QVBoxLayout()
        fullVBox.addStretch()
        fullVBox.addLayout(topHBox)
        fullVBox.addStretch()
        fullVBox.addLayout(bottomHbox)

        self.MotionPage = QWidget()
        self.MotionPage.setLayout(fullVBox)

    
    def CreateCalibrationPage(self):
        xOffsetHBox = QtGui.QHBoxLayout()
        xOffsetLabel = QLabel("X Offset: ")
        xOffsetLabel.setFont(self.PicLabelFont)
        xOffsetLabel.setFixedSize(QSize(100,50))
        self.xOffsetButton = QPushButton(str(round(self.xOffset,2)))
        self.xOffsetButton.setFont(self.PicLabelFont)
        self.xOffsetButton.setFixedSize(QSize(70,50))
        self.xOffsetButton.setStyleSheet("background-color: #AAAAAA; border: 6px solid #339A99;  border-radius: 4px;")
        
        self.xOffsetButton.setProperty("TO",4)
        self.xOffsetButton.pressed.connect(lambda:self.HighLightRectangle(self.xOffsetButton))
        self.xOffsetButton.released.connect(lambda:self.UnHighLightRectangle(self.xOffsetButton))
        self.xOffsetButton.clicked.connect(lambda:self.GoToPage(self.xOffsetButton))
        xOffsetHBox.addWidget(xOffsetLabel)
        xOffsetHBox.addWidget(self.xOffsetButton)
        
        yOffsetHBox = QtGui.QHBoxLayout()
        yOffsetLabel = QLabel("Y Offset: ")
        yOffsetLabel.setFont(self.PicLabelFont)
        yOffsetLabel.setFixedSize(QSize(100,50))
        self.yOffsetButton = QPushButton(str(round(self.yOffset,2)))
        self.yOffsetButton.setFont(self.PicLabelFont)
        self.yOffsetButton.setFixedSize(QSize(70,50))
        self.yOffsetButton.setStyleSheet("background-color: #AAAAAA;border: 6px solid #339A99;  border-radius: 4px;")
        self.yOffsetButton.setProperty("TO",5)
        self.yOffsetButton.pressed.connect(lambda:self.HighLightRectangle(self.yOffsetButton))
        self.yOffsetButton.released.connect(lambda:self.UnHighLightRectangle(self.yOffsetButton))
        self.yOffsetButton.clicked.connect(lambda:self.GoToPage(self.yOffsetButton))
        yOffsetHBox.addWidget(yOffsetLabel)
        yOffsetHBox.addWidget(self.yOffsetButton)
        
        z1OffsetHBox = QtGui.QHBoxLayout()
        z1OffsetLabel = QLabel("A Offset: ")
        z1OffsetLabel.setFont(self.PicLabelFont)
        z1OffsetLabel.setFixedSize(QSize(100,50))
        self.z1OffsetButton = QPushButton(str(round(self.z1Offset,2)))
        self.z1OffsetButton.setFont(self.PicLabelFont)
        self.z1OffsetButton.setFixedSize(QSize(70,50))
        self.z1OffsetButton.setStyleSheet("background-color: #AAAAAA; border: 6px solid #339A99; border-radius: 4px;")
        self.z1OffsetButton.setProperty("TO",6)
        self.z1OffsetButton.pressed.connect(lambda:self.HighLightRectangle(self.z1OffsetButton))
        self.z1OffsetButton.released.connect(lambda:self.UnHighLightRectangle(self.z1OffsetButton))
        self.z1OffsetButton.clicked.connect(lambda:self.GoToPage(self.z1OffsetButton))
        z1OffsetHBox.addWidget(z1OffsetLabel)
        z1OffsetHBox.addWidget(self.z1OffsetButton)
        
        z2OffsetHBox = QtGui.QHBoxLayout()
        z2OffsetLabel = QLabel("V Offset: ")
        z2OffsetLabel.setFont(self.PicLabelFont)
        z2OffsetLabel.setFixedSize(QSize(100,50))
        self.z2OffsetButton = QPushButton(str(round(self.z2Offset,2)))
        self.z2OffsetButton.setFont(self.PicLabelFont)
        self.z2OffsetButton.setFixedSize(QSize(70,50))
        self.z2OffsetButton.setStyleSheet("background-color: #AAAAAA ;border: 6px solid #339A99;  border-radius: 4px;")
        self.z2OffsetButton.setProperty("TO",7)
        self.z2OffsetButton.pressed.connect(lambda:self.HighLightRectangle(self.z2OffsetButton))
        self.z2OffsetButton.released.connect(lambda:self.UnHighLightRectangle(self.z2OffsetButton))
        self.z2OffsetButton.clicked.connect(lambda:self.GoToPage(self.z2OffsetButton))
        z2OffsetHBox.addWidget(z2OffsetLabel)
        z2OffsetHBox.addWidget(self.z2OffsetButton)
        
        
        centerZ1 = QPushButton()
        centerZ1.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/centre_A.png")))
        centerZ1.setFixedSize(QSize(80,80))
        centerZ1.setIconSize(QSize(70,70))
        centerZ1.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 40px; border-style: solid;");
        centerZ1.setProperty("NAME","Center A")
        centerZ1.setProperty("EXTRUDER","ATRIUM")
        centerZ1.pressed.connect(lambda:self.HighLightHome(centerZ1))
        centerZ1.released.connect(lambda:self.UnHighLightHome(centerZ1))
        centerZ1.clicked.connect(lambda:self.CenterZ(centerZ1))
        centerZ1Label = QLabel(centerZ1.property("NAME"))
        centerZ1Label.setFont(self.PicLabelFont)
        centerZ1Vbox = QVBoxLayout()
        centerZ1Vbox.addWidget(centerZ1)
        #centerZ1Vbox.addWidget(centerZ1Label)

        centerZ2 = QPushButton()
        centerZ2.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/centre_V.png")))
        centerZ2.setFixedSize(QSize(80,80))
        centerZ2.setIconSize(QSize(70,70))
        centerZ2.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 40px; border-style: solid;");
        centerZ2.setProperty("NAME","Center V")
        centerZ2.setProperty("EXTRUDER","VENTRICLE")
        centerZ2.pressed.connect(lambda:self.HighLightHome(centerZ2))
        centerZ2.released.connect(lambda:self.UnHighLightHome(centerZ2))
        centerZ2.clicked.connect(lambda:self.CenterZ(centerZ2))
        centerZ2Label = QLabel(centerZ2.property("NAME"))
        centerZ2Label.setFont(self.PicLabelFont)
        centerZ2Vbox = QVBoxLayout()
        centerZ2Vbox.addWidget(centerZ2)
        #centerZ2Vbox.addWidget(centerZ2Label)

        
        offsetVBox = QtGui.QVBoxLayout()
        offsetVBox.addStretch()
        offsetVBox.addStretch()
        offsetVBox.addLayout(xOffsetHBox)
        offsetVBox.addStretch()
        offsetVBox.addLayout(yOffsetHBox)
        offsetVBox.addStretch()
        offsetVBox.addLayout(z1OffsetHBox)
        offsetVBox.addStretch()
        offsetVBox.addLayout(z2OffsetHBox)
        
        self.calibrationTitle = QLabel("")
        self.calibrationTitle.setFont(self.PicLabelFont)
        self.calibrationTitle.setStyleSheet("color: #ED9D61;")
        
        atriumMeasuredHBox = QtGui.QHBoxLayout()
        atriumEmptyNameLabel = QLabel("")
        atriumEmptyNameLabel.setFont(self.PicLabelFont)
        atriumEmptyNameLabel.setFixedSize(QSize(200,50))
        atriumValueLabel = QLabel(str(round(self.atriumHeight,2)))
        atriumValueLabel.setFont(self.PicLabelFont)
        atriumValueLabel.setFixedSize(QSize(80,50))
        self.atriumMeasuredValueLabel = QLabel("-")
        self.atriumMeasuredValueLabel.setFont(self.PicLabelFont)
        self.atriumMeasuredValueLabel.setFixedSize(QSize(80,50))
        self.atriumMeasuredValueLabel.setProperty("NAME", "ATRIUM")
        self.atriumMeasuredValueLabel.setStyleSheet("color : #ED9D61")
        atriumSet = QPushButton("Set") 
        atriumSet.setStyleSheet("background-color: #AAAAAA; border: 8px solid #339A99; border-radius: 10px;")
        atriumSet.setFont(self.PicLabelFont)
        atriumSet.setFixedSize(QSize(100,50))
        atriumSet.setIconSize(QSize(100,50))
        atriumSet.pressed.connect(lambda:self.HighLightRectangle(atriumSet))
        atriumSet.released.connect(lambda:self.UnHighLightRectangle(atriumSet))
        atriumSet.clicked.connect(lambda:self.SetNeedleHeight(self.atriumMeasuredValueLabel, atriumValueLabel))
        atriumMeasuredHBox.addWidget(atriumEmptyNameLabel)
        atriumMeasuredHBox.addWidget(self.atriumMeasuredValueLabel)
        atriumMeasuredHBox.addWidget(atriumSet)
        
        atriumExistingHBox = QtGui.QHBoxLayout()
        atriumNameLabel = QLabel("Atrium Height: ")
        atriumNameLabel.setFont(self.PicLabelFont)
        atriumNameLabel.setFixedSize(QSize(200,50))
        self.atriumCalibrate = QPushButton("Find")
        self.atriumCalibrate.setStyleSheet(" QPushButton{border: 8px solid #339A99; border-radius: 50px; border-style: solid; background-color: #AAAAAA} QPushButton:pressed{background : #339A99}");
        self.atriumCalibrate.setFont(self.PicLabelFont)
        self.atriumCalibrate.setFixedSize(QSize(100,100))
        self.atriumCalibrate.setProperty("NAME", "ATRIUM")
        self.atriumCalibrate.clicked.connect(lambda:self.CalibrateNeedle(self.atriumCalibrate))
        atriumExistingHBox.addWidget(atriumNameLabel)
        atriumExistingHBox.addWidget(atriumValueLabel)
        atriumExistingHBox.addWidget(self.atriumCalibrate)
        
        ventricleMeasuredHBox = QtGui.QHBoxLayout()
        ventricleEmptyNameLabel = QLabel("")
        ventricleEmptyNameLabel.setFont(self.PicLabelFont)
        ventricleEmptyNameLabel.setFixedSize(QSize(200,50))
        self.ventricleMeasuredValueLabel = QLabel("-")
        self.ventricleMeasuredValueLabel.setFont(self.PicLabelFont)
        self.ventricleMeasuredValueLabel.setFixedSize(QSize(80,50))
        self.ventricleMeasuredValueLabel.setProperty("NAME", "VENTRICLE")
        self.ventricleMeasuredValueLabel.setStyleSheet("color : #ED9D61")
        ventricleValueLabel = QLabel(str(round(self.ventricleHeight,2)))
        ventricleValueLabel.setFont(self.PicLabelFont)
        ventricleValueLabel.setFixedSize(QSize(80,50))
        ventricleSet = QPushButton("Set") 
        ventricleSet.setStyleSheet("background-color: #AAAAAA;border: 8px solid #339A99;  border-radius: 10px;")
        ventricleSet.setFont(self.PicLabelFont)
        ventricleSet.setFixedSize(QSize(100,50))
        ventricleSet.setIconSize(QSize(100,50))
        ventricleSet.pressed.connect(lambda:self.HighLightRectangle(ventricleSet))
        ventricleSet.released.connect(lambda:self.UnHighLightRectangle(ventricleSet))
        ventricleSet.clicked.connect(lambda:self.SetNeedleHeight(self.ventricleMeasuredValueLabel, ventricleValueLabel))
        ventricleMeasuredHBox.addWidget(ventricleEmptyNameLabel)
        ventricleMeasuredHBox.addWidget(self.ventricleMeasuredValueLabel)
        ventricleMeasuredHBox.addWidget(ventricleSet)
        
        ventricleExistingHBox = QtGui.QHBoxLayout()
        ventricleNameLabel = QLabel("Ventricle Height: ")
        ventricleNameLabel.setFont(self.PicLabelFont)
        ventricleNameLabel.setFixedSize(QSize(200,50))
        self.ventricleCalibrate = QPushButton("Find")
        self.ventricleCalibrate.setStyleSheet(" border: 8px solid #339A99; border-radius: 50px; border-style: solid; background-color: #AAAAAA");
        self.ventricleCalibrate.setFont(self.PicLabelFont)
        self.ventricleCalibrate.setFixedSize(QSize(100,100))
        self.ventricleCalibrate.setProperty("NAME", "VENTRICLE")
        self.ventricleCalibrate.clicked.connect(lambda:self.CalibrateNeedle(self.ventricleCalibrate))
        ventricleExistingHBox.addWidget(ventricleNameLabel)
        ventricleExistingHBox.addWidget(ventricleValueLabel)
        ventricleExistingHBox.addWidget(self.ventricleCalibrate)
        
        needleDetectionVBox = QtGui.QVBoxLayout()
        needleDetectionVBox.addWidget(self.calibrationTitle)
        needleDetectionVBox.addStretch()
        needleDetectionVBox.addLayout(atriumExistingHBox)
        needleDetectionVBox.addStretch()
        needleDetectionVBox.addLayout(atriumMeasuredHBox)
        needleDetectionVBox.addStretch()
        needleDetectionVBox.addStretch()
        needleDetectionVBox.addLayout(ventricleExistingHBox)
        needleDetectionVBox.addStretch()
        needleDetectionVBox.addLayout(ventricleMeasuredHBox)
        needleDetectionVBox.addStretch()
        
        topHBox = QtGui.QHBoxLayout()
        topHBox.addStretch()
        topHBox.addLayout(offsetVBox)
        topHBox.addStretch()
        topHBox.addStretch()
        topHBox.addStretch()
        topHBox.addLayout(needleDetectionVBox)
        topHBox.addStretch()
        
        #self.calibrationFrame.setLayout(topHBox)
        #self.calibrationFrame.show()
        
        bottomHBox = QtGui.QHBoxLayout()
        back = QPushButton()
        back.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/back.png")))
        back.setFixedSize(QSize(190,115))
        back.setIconSize(QSize(150,75))
        back.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px} ")
        back.setProperty("NAME","Back TO MCU")
        back.setProperty("TO",1)
        back.clicked.connect(lambda:self.GoToPage(back))
        reset = QPushButton("Reset") 
        reset.setStyleSheet("background-color: #AAAAAA; border: 8px solid #339A99; border-radius: 10px;")
        reset.setFont(self.MediumLabelFont)
        reset.setFixedSize(QSize(150,75))
        reset.setIconSize(QSize(150,75))
        reset.pressed.connect(lambda:self.HighLightRectangle(reset))
        reset.released.connect(lambda:self.UnHighLightRectangle(reset))
        reset.clicked.connect(lambda:self.Reconnect())
        bottomHBox.addStretch()
        bottomHBox.addLayout(centerZ1Vbox)
        bottomHBox.addStretch()
        bottomHBox.addLayout(centerZ2Vbox)
        bottomHBox.addStretch()
        bottomHBox.addWidget(reset)
        bottomHBox.addStretch()
        bottomHBox.addStretch()
        bottomHBox.addStretch()
        bottomHBox.addStretch()
        bottomHBox.addWidget(back)

        fullVBox = QtGui.QVBoxLayout()
        fullVBox.addStretch()
        fullVBox.addLayout(topHBox)
        fullVBox.addStretch()
        fullVBox.addLayout(bottomHBox)
        
        self.CalibrationPage = QWidget()
        self.CalibrationPage.setLayout(fullVBox)
    
    
    def CreateEditXOffsetPage(self):
        editGrid = QGridLayout()
        bSign = QLabel(" ")
        bSign.setFont(self.BigLabelFont)
        
        if(self.xOffset>=0):
            bSign.setText(" ")
        else:
            bSign.setText("-")
        
        p = int(abs (round(self.xOffset,2) * 100))

        nameLabel = QLabel("   X offset")   
        nameLabel.setFont(self.BigLabelFont)

        bDot = QLabel(".")
        bDot.setFont(self.BigLabelFont)
        
        
        b4Label = QLabel(str(int(p%10)))
        b4Label.setFont(self.BigLabelFont)
        b4Label.setProperty("TO",3)
        b4Label.setProperty("NAME","X")
        b4Label.setProperty("MULTIPLIER",1)
        p /= 10
        b3Label = QLabel(str(int(p%10)))
        b3Label.setFont(self.BigLabelFont)
        b3Label.setProperty("TO",3)
        b3Label.setProperty("NAME","X")
        b3Label.setProperty("MULTIPLIER",10)
        p /= 10
        b2Label = QLabel(str(int(p%10)))   
        b2Label.setFont(self.BigLabelFont)
        b2Label.setProperty("TO",3)
        b2Label.setProperty("NAME","X")
        b2Label.setProperty("MULTIPLIER",100)
        p /= 10
        b1Label = QLabel(str(int(p%10)))   
        b1Label.setFont(self.BigLabelFont) 
        b1Label.setProperty("TO",3)
        b1Label.setProperty("NAME","X")
        b1Label.setProperty("MULTIPLIER",1000)

        b1 = QPushButton()
        b1.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/up-arrow.png")))
        b1.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b1.setFixedSize(QSize(100,100))
        b1.setIconSize(QSize(100,100))
        b1.setProperty("DIRECTION",1)
        b1.clicked.connect(lambda:self.ChangeOffset(b1,b1Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b2 = QPushButton()
        b2.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/down-arrow.png")))
        b2.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b2.setFixedSize(QSize(100,100))
        b2.setIconSize(QSize(100,100))
        b2.setProperty("DIRECTION",-1)
        b2.clicked.connect(lambda:self.ChangeOffset(b2,b1Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b3 = QPushButton()
        b3.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/up-arrow.png")))
        b3.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b3.setFixedSize(QSize(100,100))
        b3.setIconSize(QSize(100,100))
        b3.setProperty("DIRECTION",1)
        b3.clicked.connect(lambda:self.ChangeOffset(b3,b2Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b4 = QPushButton()
        b4.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/down-arrow.png")))
        b4.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b4.setFixedSize(QSize(100,100))
        b4.setIconSize(QSize(100,100))
        b4.setProperty("DIRECTION",-1)
        b4.clicked.connect(lambda:self.ChangeOffset(b4,b2Label,bSign,b1Label,b2Label,b3Label,b4Label))

        b5 = QPushButton()
        b5.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/up-arrow.png")))
        b5.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b5.setFixedSize(QSize(100,100))
        b5.setIconSize(QSize(100,100))
        b5.setProperty("DIRECTION",1)
        b5.clicked.connect(lambda:self.ChangeOffset(b5,b3Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b6 = QPushButton()
        b6.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/down-arrow.png")))
        b6.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b6.setFixedSize(QSize(100,100))
        b6.setIconSize(QSize(100,100))
        b6.setProperty("DIRECTION",-1)
        b6.clicked.connect(lambda:self.ChangeOffset(b6,b3Label,bSign,b1Label,b2Label,b3Label,b4Label))

        b7 = QPushButton()
        b7.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/up-arrow.png")))
        b7.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b7.setFixedSize(QSize(100,100))
        b7.setIconSize(QSize(100,100))
        b7.setProperty("DIRECTION",1)
        b7.clicked.connect(lambda:self.ChangeOffset(b7,b4Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b8 = QPushButton()
        b8.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/down-arrow.png")))
        b8.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b8.setFixedSize(QSize(100,100))
        b8.setIconSize(QSize(100,100))
        b8.setProperty("DIRECTION",-1)
        b8.clicked.connect(lambda:self.ChangeOffset(b8,b4Label,bSign,b1Label,b2Label,b3Label,b4Label))

        unitLabel = QLabel("mm")   
        unitLabel.setFont(self.MediumLabelFont) 
        
        editGrid.addWidget(b1,0,1)
        editGrid.addWidget(b2,2,1)
        editGrid.addWidget(b3,0,2)
        editGrid.addWidget(b4,2,2)
        editGrid.addWidget(b5,0,4)
        editGrid.addWidget(b6,2,4)
        editGrid.addWidget(b7,0,5)
        editGrid.addWidget(b8,2,5)
        editGrid.addWidget(b1Label,1,1,Qt.AlignCenter)
        editGrid.addWidget(b2Label,1,2,Qt.AlignCenter)
        editGrid.addWidget(b3Label,1,4,Qt.AlignCenter)
        editGrid.addWidget(b4Label,1,5,Qt.AlignCenter)
        editGrid.addWidget(bDot,1,3,Qt.AlignCenter)
        editGrid.addWidget(bSign,1,0,Qt.AlignCenter)
        editGrid.addWidget(unitLabel,1,6,Qt.AlignCenter)

        editHBox = QtGui.QHBoxLayout()
        editHBox.addStretch()
        editHBox.addLayout(editGrid)
        editHBox.addStretch()

        bottomHBox = QtGui.QHBoxLayout()
        back = QPushButton()
        back.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/back.png")))
        back.setFixedSize(QSize(190,115))
        back.setIconSize(QSize(150,75))
        back.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px} ")
        back.setProperty("ID","X")
        back.setProperty("TO",3)
        back.clicked.connect(lambda:self.ResetEditPage(back,bSign,b1Label, b2Label, b3Label, b4Label))
        setButton = QPushButton("Set") 
        setButton.setStyleSheet("background-color: #AAAAAA; border: 8px solid #339A99;  border-radius: 10px;")
        setButton.setFont(self.MediumLabelFont)
        setButton.setFixedSize(QSize(150,75))
        setButton.setIconSize(QSize(150,75))
        setButton.pressed.connect(lambda:self.HighLightRectangle(setButton))
        setButton.released.connect(lambda:self.UnHighLightRectangle(setButton))
        setButton.clicked.connect(lambda:self.SetOffset(bSign, b1Label,b2Label,b3Label, b4Label))
        bottomHBox.addStretch()
        bottomHBox.addWidget(setButton)
        bottomHBox.addWidget(back)

        fullVBox = QtGui.QVBoxLayout()
        fullVBox.addStretch()
        fullVBox.addWidget(nameLabel)
        fullVBox.addStretch()
        fullVBox.addLayout(editHBox)
        fullVBox.addStretch()
        fullVBox.addLayout(bottomHBox)
        
        self.EditXOffsetPage = QWidget()
        self.EditXOffsetPage.setLayout(fullVBox)

    
    def CreateEditYOffsetPage(self):
        editGrid = QGridLayout()
        
        bSign = QLabel(" ")
        bSign.setFont(self.BigLabelFont)
        
        if(self.yOffset>=0):
            bSign.setText(" ")
        else:
            bSign.setText("-")
        
        p = int(abs(round(self.yOffset,2) * 100))

        nameLabel = QLabel("   Y offset")   
        nameLabel.setFont(self.BigLabelFont)

        bDot = QLabel(".")
        bDot.setFont(self.BigLabelFont)
        
        b4Label = QLabel(str(int(p%10)))
        b4Label.setFont(self.BigLabelFont)
        b4Label.setProperty("TO",3)
        b4Label.setProperty("NAME","Y")
        b4Label.setProperty("MULTIPLIER",1)
        p /= 10
        b3Label = QLabel(str(int(p%10)))
        b3Label.setFont(self.BigLabelFont)
        b3Label.setProperty("TO",3)
        b3Label.setProperty("NAME","Y")
        b3Label.setProperty("MULTIPLIER",10)
        p /= 10
        b2Label = QLabel(str(int(p%10)))   
        b2Label.setFont(self.BigLabelFont)
        b2Label.setProperty("TO",3)
        b2Label.setProperty("NAME","Y")
        b2Label.setProperty("MULTIPLIER",100)
        p /= 10
        b1Label = QLabel(str(int(p%10)))   
        b1Label.setFont(self.BigLabelFont) 
        b1Label.setProperty("TO",3)
        b1Label.setProperty("NAME","Y")
        b1Label.setProperty("MULTIPLIER",1000)

        b1 = QPushButton()
        b1.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/up-arrow.png")))
        b1.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b1.setFixedSize(QSize(100,100))
        b1.setIconSize(QSize(100,100))
        b1.setProperty("DIRECTION",1)
        b1.clicked.connect(lambda:self.ChangeOffset(b1,b1Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b2 = QPushButton()
        b2.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/down-arrow.png")))
        b2.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b2.setFixedSize(QSize(100,100))
        b2.setIconSize(QSize(100,100))
        b2.setProperty("DIRECTION",-1)
        b2.clicked.connect(lambda:self.ChangeOffset(b2,b1Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b3 = QPushButton()
        b3.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/up-arrow.png")))
        b3.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b3.setFixedSize(QSize(100,100))
        b3.setIconSize(QSize(100,100))
        b3.setProperty("DIRECTION",1)
        b3.clicked.connect(lambda:self.ChangeOffset(b3,b2Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b4 = QPushButton()
        b4.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/down-arrow.png")))
        b4.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b4.setFixedSize(QSize(100,100))
        b4.setIconSize(QSize(100,100))
        b4.setProperty("DIRECTION",-1)
        b4.clicked.connect(lambda:self.ChangeOffset(b4,b2Label,bSign,b1Label,b2Label,b3Label,b4Label))

        b5 = QPushButton()
        b5.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/up-arrow.png")))
        b5.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b5.setFixedSize(QSize(100,100))
        b5.setIconSize(QSize(100,100))
        b5.setProperty("DIRECTION",1)
        b5.clicked.connect(lambda:self.ChangeOffset(b5,b3Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b6 = QPushButton()
        b6.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/down-arrow.png")))
        b6.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b6.setFixedSize(QSize(100,100))
        b6.setIconSize(QSize(100,100))
        b6.setProperty("DIRECTION",-1)
        b6.clicked.connect(lambda:self.ChangeOffset(b6,b3Label,bSign,b1Label,b2Label,b3Label,b4Label))

        b7 = QPushButton()
        b7.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/up-arrow.png")))
        b7.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b7.setFixedSize(QSize(100,100))
        b7.setIconSize(QSize(100,100))
        b7.setProperty("DIRECTION",1)
        b7.clicked.connect(lambda:self.ChangeOffset(b7,b4Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b8 = QPushButton()
        b8.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/down-arrow.png")))
        b8.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b8.setFixedSize(QSize(100,100))
        b8.setIconSize(QSize(100,100))
        b8.setProperty("DIRECTION",-1)
        b8.clicked.connect(lambda:self.ChangeOffset(b8,b4Label,bSign,b1Label,b2Label,b3Label,b4Label))

        unitLabel = QLabel("mm")   
        unitLabel.setFont(self.MediumLabelFont) 
        
        editGrid.addWidget(b1,0,1)
        editGrid.addWidget(b2,2,1)
        editGrid.addWidget(b3,0,2)
        editGrid.addWidget(b4,2,2)
        editGrid.addWidget(b5,0,4)
        editGrid.addWidget(b6,2,4)
        editGrid.addWidget(b7,0,5)
        editGrid.addWidget(b8,2,5)
        editGrid.addWidget(b1Label,1,1,Qt.AlignCenter)
        editGrid.addWidget(b2Label,1,2,Qt.AlignCenter)
        editGrid.addWidget(b3Label,1,4,Qt.AlignCenter)
        editGrid.addWidget(b4Label,1,5,Qt.AlignCenter)
        editGrid.addWidget(bDot,1,3,Qt.AlignCenter)
        editGrid.addWidget(bSign,1,0,Qt.AlignCenter)
        editGrid.addWidget(unitLabel,1,6,Qt.AlignCenter)

        editHBox = QtGui.QHBoxLayout()
        editHBox.addStretch()
        editHBox.addLayout(editGrid)
        editHBox.addStretch()

        bottomHBox = QtGui.QHBoxLayout()
        back = QPushButton()
        back.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/back.png")))
        back.setFixedSize(QSize(190,115))
        back.setIconSize(QSize(150,75))
        back.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px} ")
        back.setProperty("ID","Y")
        back.setProperty("TO",3)
        back.clicked.connect(lambda:self.ResetEditPage(back,bSign,b1Label, b2Label, b3Label, b4Label))
        setButton = QPushButton("Set") 
        setButton.setStyleSheet("background-color: #AAAAAA; border: 8px solid #339A99;  border-radius: 10px;")
        setButton.setFont(self.MediumLabelFont)
        setButton.setFixedSize(QSize(150,75))
        setButton.setIconSize(QSize(150,75))
        setButton.pressed.connect(lambda:self.HighLightRectangle(setButton))
        setButton.released.connect(lambda:self.UnHighLightRectangle(setButton))
        setButton.clicked.connect(lambda:self.SetOffset(bSign, b1Label,b2Label,b3Label, b4Label))
        bottomHBox.addStretch()
        bottomHBox.addWidget(setButton)
        bottomHBox.addWidget(back)
        
        fullVBox = QtGui.QVBoxLayout()
        fullVBox.addStretch()
        fullVBox.addWidget(nameLabel)
        fullVBox.addStretch()
        fullVBox.addLayout(editHBox)
        fullVBox.addStretch()
        fullVBox.addLayout(bottomHBox)
        
        self.EditYOffsetPage = QWidget()
        self.EditYOffsetPage.setLayout(fullVBox)

    
    def CreateEditZ1OffsetPage(self):
        editGrid = QGridLayout()
        
        bSign = QLabel(" ")
        bSign.setFont(self.BigLabelFont)
        
        if(self.z1Offset >=0):
            bSign.setText(" ")
        else:
            bSign.setText("-")
        
        p = int(abs(round(self.z1Offset,2) * 100))

        nameLabel = QLabel("   Atrium offset")   
        nameLabel.setFont(self.BigLabelFont)

        bDot = QLabel(".")
        bDot.setFont(self.BigLabelFont)
        
        b4Label = QLabel(str(int(p%10)))
        b4Label.setFont(self.BigLabelFont)
        b4Label.setProperty("TO",3)
        b4Label.setProperty("NAME","Z1")
        b4Label.setProperty("MULTIPLIER",1)
        p /= 10
        b3Label = QLabel(str(int(p%10)))
        b3Label.setFont(self.BigLabelFont)
        b3Label.setProperty("TO",3)
        b3Label.setProperty("NAME","Z1")
        b3Label.setProperty("MULTIPLIER",10)
        p /= 10
        b2Label = QLabel(str(int(p%10)))   
        b2Label.setFont(self.BigLabelFont)
        b2Label.setProperty("TO",3)
        b2Label.setProperty("NAME","Z1")
        b2Label.setProperty("MULTIPLIER",100)
        p /= 10
        b1Label = QLabel(str(int(p%10)))   
        b1Label.setFont(self.BigLabelFont) 
        b1Label.setProperty("TO",3)
        b1Label.setProperty("NAME","Z1")
        b1Label.setProperty("MULTIPLIER",1000)

        b1 = QPushButton()
        b1.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/up-arrow.png")))
        b1.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b1.setFixedSize(QSize(100,100))
        b1.setIconSize(QSize(100,100))
        b1.setProperty("DIRECTION",1)
        b1.clicked.connect(lambda:self.ChangeOffset(b1,b1Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b2 = QPushButton()
        b2.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/down-arrow.png")))
        b2.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b2.setFixedSize(QSize(100,100))
        b2.setIconSize(QSize(100,100))
        b2.setProperty("DIRECTION",-1)
        b2.clicked.connect(lambda:self.ChangeOffset(b2,b1Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b3 = QPushButton()
        b3.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/up-arrow.png")))
        b3.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b3.setFixedSize(QSize(100,100))
        b3.setIconSize(QSize(100,100))
        b3.setProperty("DIRECTION",1)
        b3.clicked.connect(lambda:self.ChangeOffset(b3,b2Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b4 = QPushButton()
        b4.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/down-arrow.png")))
        b4.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b4.setFixedSize(QSize(100,100))
        b4.setIconSize(QSize(100,100))
        b4.setProperty("DIRECTION",-1)
        b4.clicked.connect(lambda:self.ChangeOffset(b4,b2Label,bSign,b1Label,b2Label,b3Label,b4Label))

        b5 = QPushButton()
        b5.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/up-arrow.png")))
        b5.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b5.setFixedSize(QSize(100,100))
        b5.setIconSize(QSize(100,100))
        b5.setProperty("DIRECTION",1)
        b5.clicked.connect(lambda:self.ChangeOffset(b5,b3Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b6 = QPushButton()
        b6.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/down-arrow.png")))
        b6.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b6.setFixedSize(QSize(100,100))
        b6.setIconSize(QSize(100,100))
        b6.setProperty("DIRECTION",-1)
        b6.clicked.connect(lambda:self.ChangeOffset(b6,b3Label,bSign,b1Label,b2Label,b3Label,b4Label))

        b7 = QPushButton()
        b7.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/up-arrow.png")))
        b7.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b7.setFixedSize(QSize(100,100))
        b7.setIconSize(QSize(100,100))
        b7.setProperty("DIRECTION",1)
        b7.clicked.connect(lambda:self.ChangeOffset(b7,b4Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b8 = QPushButton()
        b8.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/down-arrow.png")))
        b8.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b8.setFixedSize(QSize(100,100))
        b8.setIconSize(QSize(100,100))
        b8.setProperty("DIRECTION",-1)
        b8.clicked.connect(lambda:self.ChangeOffset(b8,b4Label,bSign,b1Label,b2Label,b3Label,b4Label))

        unitLabel = QLabel("mm")   
        unitLabel.setFont(self.MediumLabelFont) 
        
        editGrid.addWidget(b1,0,1)
        editGrid.addWidget(b2,2,1)
        editGrid.addWidget(b3,0,2)
        editGrid.addWidget(b4,2,2)
        editGrid.addWidget(b5,0,4)
        editGrid.addWidget(b6,2,4)
        editGrid.addWidget(b7,0,5)
        editGrid.addWidget(b8,2,5)
        editGrid.addWidget(b1Label,1,1,Qt.AlignCenter)
        editGrid.addWidget(b2Label,1,2,Qt.AlignCenter)
        editGrid.addWidget(b3Label,1,4,Qt.AlignCenter)
        editGrid.addWidget(b4Label,1,5,Qt.AlignCenter)
        editGrid.addWidget(bDot,1,3,Qt.AlignCenter)
        editGrid.addWidget(bSign,1,0,Qt.AlignCenter)
        editGrid.addWidget(unitLabel,1,6,Qt.AlignCenter)

        editHBox = QtGui.QHBoxLayout()
        editHBox.addStretch()
        editHBox.addLayout(editGrid)
        editHBox.addStretch()

        bottomHBox = QtGui.QHBoxLayout()
        back = QPushButton()
        back.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/back.png")))
        back.setFixedSize(QSize(190,115))
        back.setIconSize(QSize(150,75))
        back.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px} ")
        back.setProperty("ID","Z1")
        back.setProperty("TO",3)
        back.clicked.connect(lambda:self.ResetEditPage(back,bSign,b1Label, b2Label, b3Label, b4Label))
        setButton = QPushButton("Set") 
        setButton.setStyleSheet("background-color: #AAAAAA; border: 8px solid #339A99;  border-radius: 10px;")
        setButton.setFont(self.MediumLabelFont)
        setButton.setFixedSize(QSize(150,75))
        setButton.setIconSize(QSize(150,75))
        setButton.pressed.connect(lambda:self.HighLightRectangle(setButton))
        setButton.released.connect(lambda:self.UnHighLightRectangle(setButton))
        setButton.clicked.connect(lambda:self.SetOffset(bSign, b1Label,b2Label,b3Label, b4Label))
        bottomHBox.addStretch()
        bottomHBox.addWidget(setButton)
        bottomHBox.addWidget(back)

        fullVBox = QtGui.QVBoxLayout()
        fullVBox.addStretch()
        fullVBox.addWidget(nameLabel)
        fullVBox.addStretch()
        fullVBox.addLayout(editHBox)
        fullVBox.addStretch()
        fullVBox.addLayout(bottomHBox)
        
        self.EditZ1OffsetPage = QWidget()
        self.EditZ1OffsetPage.setLayout(fullVBox)

    
    def CreateEditZ2OffsetPage(self):
        editGrid = QGridLayout()
        
        bSign = QLabel(" ")
        bSign.setFont(self.BigLabelFont)
        
        if(self.z2Offset>=0):
            bSign.setText(" ")
        else:
            bSign.setText("-")
        
        p = int(abs(round(self.z2Offset,2) * 100))

        nameLabel = QLabel("   Ventricle offset")   
        nameLabel.setFont(self.BigLabelFont)


        bDot = QLabel(".")
        bDot.setFont(self.BigLabelFont)
        
        b4Label = QLabel(str(int(p%10)))
        b4Label.setFont(self.BigLabelFont)
        b4Label.setProperty("TO",3)
        b4Label.setProperty("NAME","Z2")
        b4Label.setProperty("MULTIPLIER",1)
        p /= 10
        b3Label = QLabel(str(int(p%10)))
        b3Label.setFont(self.BigLabelFont)
        b3Label.setProperty("TO",3)
        b3Label.setProperty("NAME","Z2")
        b3Label.setProperty("MULTIPLIER",10)
        p /= 10
        b2Label = QLabel(str(int(p%10)))   
        b2Label.setFont(self.BigLabelFont)
        b2Label.setProperty("TO",3)
        b2Label.setProperty("NAME","Z2")
        b2Label.setProperty("MULTIPLIER",100)
        p /= 10
        b1Label = QLabel(str(int(p%10)))   
        b1Label.setFont(self.BigLabelFont) 
        b1Label.setProperty("TO",3)
        b1Label.setProperty("NAME","Z2")
        b1Label.setProperty("MULTIPLIER",1000)

        b1 = QPushButton()
        b1.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/up-arrow.png")))
        b1.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b1.setFixedSize(QSize(100,100))
        b1.setIconSize(QSize(100,100))
        b1.setProperty("DIRECTION",1)
        b1.clicked.connect(lambda:self.ChangeOffset(b1,b1Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b2 = QPushButton()
        b2.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/down-arrow.png")))
        b2.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b2.setFixedSize(QSize(100,100))
        b2.setIconSize(QSize(100,100))
        b2.setProperty("DIRECTION",-1)
        b2.clicked.connect(lambda:self.ChangeOffset(b2,b1Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b3 = QPushButton()
        b3.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/up-arrow.png")))
        b3.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b3.setFixedSize(QSize(100,100))
        b3.setIconSize(QSize(100,100))
        b3.setProperty("DIRECTION",1)
        b3.clicked.connect(lambda:self.ChangeOffset(b3,b2Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b4 = QPushButton()
        b4.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/down-arrow.png")))
        b4.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b4.setFixedSize(QSize(100,100))
        b4.setIconSize(QSize(100,100))
        b4.setProperty("DIRECTION",-1)
        b4.clicked.connect(lambda:self.ChangeOffset(b4,b2Label,bSign,b1Label,b2Label,b3Label,b4Label))

        b5 = QPushButton()
        b5.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/up-arrow.png")))
        b5.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b5.setFixedSize(QSize(100,100))
        b5.setIconSize(QSize(100,100))
        b5.setProperty("DIRECTION",1)
        b5.clicked.connect(lambda:self.ChangeOffset(b5,b3Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b6 = QPushButton()
        b6.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/down-arrow.png")))
        b6.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b6.setFixedSize(QSize(100,100))
        b6.setIconSize(QSize(100,100))
        b6.setProperty("DIRECTION",-1)
        b6.clicked.connect(lambda:self.ChangeOffset(b6,b3Label,bSign,b1Label,b2Label,b3Label,b4Label))

        b7 = QPushButton()
        b7.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/up-arrow.png")))
        b7.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b7.setFixedSize(QSize(100,100))
        b7.setIconSize(QSize(100,100))
        b7.setProperty("DIRECTION",1)
        b7.clicked.connect(lambda:self.ChangeOffset(b7,b4Label,bSign,b1Label,b2Label,b3Label,b4Label)) 

        b8 = QPushButton()
        b8.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/down-arrow.png")))
        b8.setStyleSheet("background : #AAAAAA; border-radius : 10;")
        b8.setFixedSize(QSize(100,100))
        b8.setIconSize(QSize(100,100))
        b8.setProperty("DIRECTION",-1)
        b8.clicked.connect(lambda:self.ChangeOffset(b8,b4Label,bSign,b1Label,b2Label,b3Label,b4Label))

        unitLabel = QLabel("mm")   
        unitLabel.setFont(self.MediumLabelFont) 
        
        editGrid.addWidget(b1,0,1)
        editGrid.addWidget(b2,2,1)
        editGrid.addWidget(b3,0,2)
        editGrid.addWidget(b4,2,2)
        editGrid.addWidget(b5,0,4)
        editGrid.addWidget(b6,2,4)
        editGrid.addWidget(b7,0,5)
        editGrid.addWidget(b8,2,5)
        editGrid.addWidget(b1Label,1,1,Qt.AlignCenter)
        editGrid.addWidget(b2Label,1,2,Qt.AlignCenter)
        editGrid.addWidget(b3Label,1,4,Qt.AlignCenter)
        editGrid.addWidget(b4Label,1,5,Qt.AlignCenter)
        editGrid.addWidget(bDot,1,3,Qt.AlignCenter)
        editGrid.addWidget(bSign,1,0,Qt.AlignCenter)
        editGrid.addWidget(unitLabel,1,6,Qt.AlignCenter)

        editHBox = QtGui.QHBoxLayout()
        editHBox.addStretch()
        editHBox.addLayout(editGrid)
        editHBox.addStretch()

        bottomHBox = QtGui.QHBoxLayout()
        back = QPushButton()
        back.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/back.png")))
        back.setFixedSize(QSize(190,115))
        back.setIconSize(QSize(150,75))
        back.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px} ")
        back.setProperty("ID","Z2")
        back.setProperty("TO",3)
        back.clicked.connect(lambda:self.ResetEditPage(back,bSign,b1Label, b2Label, b3Label, b4Label))
        setButton = QPushButton("Set") 
        setButton.setStyleSheet("background-color: #AAAAAA; border: 8px solid #339A99;  border-radius: 10px;")
        setButton.setFont(self.MediumLabelFont)
        setButton.setFixedSize(QSize(150,75))
        setButton.setIconSize(QSize(150,75))
        setButton.pressed.connect(lambda:self.HighLightRectangle(setButton))
        setButton.released.connect(lambda:self.UnHighLightRectangle(setButton))
        setButton.clicked.connect(lambda:self.SetOffset(bSign, b1Label,b2Label,b3Label, b4Label))
        bottomHBox.addStretch()
        bottomHBox.addWidget(setButton)
        bottomHBox.addWidget(back)

        fullVBox = QtGui.QVBoxLayout()
        fullVBox.addStretch()
        fullVBox.addWidget(nameLabel)
        fullVBox.addStretch()
        fullVBox.addLayout(editHBox)
        fullVBox.addStretch()
        fullVBox.addLayout(bottomHBox)
        
        self.EditZ2OffsetPage = QWidget()
        self.EditZ2OffsetPage.setLayout(fullVBox)

    def CreateUVPage(self):
        atriumVBox = QtGui.QVBoxLayout()
        atriumCuringLabel = QLabel("  Atrium Curing")   
        atriumCuringLabel.setFixedSize(QSize(300,75))
        atriumCuringLabel.setFont(self.PicLabelFont)
        atriumCuringLabel.setAlignment(Qt.AlignLeft)
        slAtrium = QSlider(Qt.Horizontal)
        slAtrium.setMinimum(0)
        slAtrium.setFixedSize(QSize(300,150))
        slAtrium.setMaximum(100)
        slAtrium.setValue(50)
        slAtrium.setTickInterval(1)
        slAtriumLabel = QLabel(str(slAtrium.value()))   
        slAtriumLabel.setFont(self.MediumLabelFont)
        slAtriumLabel.setFixedSize(QSize(50,50))
        slAtrium.valueChanged.connect(lambda:self.CuringIntensity(slAtrium, slAtriumLabel))
        
        atrium = QPushButton("A")
        atrium.setProperty("NAME", "ATRIUM")
        atrium.setProperty("STATE", "OFF")
        atrium.setFixedSize(QSize(200,200))
        atrium.setFont(self.HugeLabelFont)
        atrium.setStyleSheet("border: 8px solid #339A99; border-radius: 100px; border-style: solid; background : #AAAAAA");
        atrium.clicked.connect(lambda:self.Curing(atrium))
        atrium.setProperty("NAME","ATRIUM")
        atriumVBox.addStretch()
        atriumVBox.addStretch()
        atriumVBox.addStretch()
        atriumVBox.addWidget(atrium)
        atriumVBox.addStretch()
        atriumVBox.addWidget(atriumCuringLabel)
        atriumVBox.addStretch()
        
        ventricleVBox = QtGui.QVBoxLayout()
        ventricleCuringLabel = QLabel("Ventricle Curing") 
        ventricleCuringLabel.setFixedSize(QSize(300,75))  
        ventricleCuringLabel.setFont(self.PicLabelFont)
        ventricleCuringLabel.setAlignment(Qt.AlignLeft)
        slVentricle = QSlider(Qt.Horizontal)
        slVentricle.setMinimum(0)
        slVentricle.setFixedSize(QSize(300,150))
        slVentricle.setMaximum(100)
        slVentricle.setValue(50)
        slVentricle.setTickInterval(1)
        slVentricleLabel = QLabel(str(slVentricle.value()))   
        slVentricleLabel.setFont(self.MediumLabelFont)
        slVentricleLabel.setFixedSize(QSize(50,50))
        slVentricle.valueChanged.connect(lambda:self.CuringIntensity(slVentricle, slVentricleLabel))
        
        ventricle = QPushButton("V")
        ventricle.setProperty("NAME", "VENTRICLE")
        ventricle.setProperty("STATE", "OFF")
        ventricle.setFixedSize(QSize(200,200))
        ventricle.setFont(self.HugeLabelFont)
        ventricle.setStyleSheet("border: 8px solid #339A99; border-radius: 100px; border-style: solid; background : #AAAAAA");
        ventricle.clicked.connect(lambda:self.Curing(ventricle))
        ventricle.setProperty("NAME","VENTRICLE")
        ventricleVBox.addStretch()
        ventricleVBox.addStretch()
        ventricleVBox.addStretch()
        ventricleVBox.addWidget(ventricle,Qt.AlignCenter)
        ventricleVBox.addStretch()
        ventricleVBox.addWidget(ventricleCuringLabel)
        ventricleVBox.addStretch()
        
        topHBox = QtGui.QHBoxLayout()
        topHBox.addStretch()
        topHBox.addStretch()
        topHBox.addStretch()
        topHBox.addStretch()
        topHBox.addLayout(atriumVBox)
        topHBox.addStretch()
        topHBox.addLayout(ventricleVBox)
        topHBox.addStretch()
        topHBox.addStretch()
        
        bottomHBox = QtGui.QHBoxLayout()
        back = QPushButton()
        back.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/back.png")))
        back.setFixedSize(QSize(190,115))
        back.setIconSize(QSize(150,75))
        back.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px} ")
        back.setProperty("TO",1)
        back.clicked.connect(lambda:self.GoToPage(back))
        bottomHBox.addStretch()
        bottomHBox.addWidget(back)

        fullVBox = QtGui.QVBoxLayout()
        fullVBox.addStretch()
        fullVBox.addStretch()
        fullVBox.addLayout(topHBox)
        fullVBox.addStretch()
        fullVBox.addLayout(bottomHBox)
        
        self.UVPage = QWidget()
        self.UVPage.setLayout(fullVBox)
        
    
    def CreatePrintPage(self):
        grid = QGridLayout()
        infoGrid = QGridLayout()
        
        
        nameLabel = QLabel("Name: ")
        nameLabel.setFont(self.PicLabelFont)
        nameLabel.setFixedSize(QSize(80,50))
        self.printNameValue = QLabel(str(self.gCodeFile))
        self.printNameValue.setFont(self.PicLabelFont)
        self.printNameValue.setFixedSize(QSize(150,50))
        
        speedLabel = QLabel("Speed: ")
        speedLabel.setFont(self.PicLabelFont)
        speedLabel.setFixedSize(QSize(80,50))
        self.printSpeedValue = QLabel(str(self.gCodeFile))
        self.printSpeedValue.setFont(self.PicLabelFont)
        self.printSpeedValue.setFixedSize(QSize(150,50))
        
        timeLabel = QLabel("Time: ")
        timeLabel.setFont(self.PicLabelFont)
        timeLabel.setFixedSize(QSize(80,50))
        self.printTimeValue = QLabel("-")
        self.printTimeValue.setFont(self.PicLabelFont)
        self.printTimeValue.setFixedSize(QSize(150,50))
        
        uvLabel = QLabel("UV: ")
        uvLabel.setFont(self.PicLabelFont)
        uvLabel.setFixedSize(QSize(80,50))
        self.printUVValue = QLabel("-")
        self.printUVValue.setFont(self.PicLabelFont)
        self.printUVValue.setFixedSize(QSize(150,50))
        
        needleLabel = QLabel("Needle: ")
        needleLabel.setFont(self.PicLabelFont)
        needleLabel.setFixedSize(QSize(80,50))
        self.printNeedleValue = QLabel("-")
        self.printNeedleValue.setFont(self.PicLabelFont)
        self.printNeedleValue.setFixedSize(QSize(150,50))
        
        materialLabel = QLabel("Material: ")
        materialLabel.setFont(self.PicLabelFont)
        materialLabel.setFixedSize(QSize(80,50))
        self.printMaterialValue = QLabel("-")
        self.printMaterialValue.setFont(self.PicLabelFont)
        self.printMaterialValue.setFixedSize(QSize(150,50))
        
        pressureLabel = QLabel("Pressure: ")
        pressureLabel.setFont(self.PicLabelFont)
        pressureLabel.setFixedSize(QSize(80,50))
        self.printPressureValue = QLabel("-")
        self.printPressureValue.setFont(self.PicLabelFont)
        self.printPressureValue.setFixedSize(QSize(150,50))
        
        infoGrid.addWidget(nameLabel,0,0)
        infoGrid.addWidget(self.printNameValue,0,1)
        infoGrid.addWidget(speedLabel,1,0)
        infoGrid.addWidget(self.printSpeedValue,1,1)
        infoGrid.addWidget(timeLabel,2,0)
        infoGrid.addWidget(self.printTimeValue,2,1)
        infoGrid.addWidget(uvLabel,3,0)
        infoGrid.addWidget(self.printUVValue,3,1)
        #infoGrid.addWidget(needleLabel,4,0)
        #infoGrid.addWidget(self.printNeedleValue,4,1)
        #infoGrid.addWidget(materialLabel,5,0)
        #infoGrid.addWidget(self.printMaterialValue,5,1)
        #infoGrid.addWidget(pressureLabel,6,0)
        #infoGrid.addWidget(self.printPressureValue,6,1)

        b1 = QPushButton()
        b1.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/loadFile.png")))
        b1.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 20;} ")
        b1.setFixedSize(QSize(150,150))
        b1.setIconSize(QSize(150,150))
        b1.setProperty("TO",15)
        b1.clicked.connect(lambda:self.LoadFileClicked(b1))
        b1Label = QLabel("Load File")
        b1Label.setFont(self.PicLabelFont)
        b1Label.setAlignment(Qt.AlignCenter)
        loadVBox = QtGui.QVBoxLayout()
        loadVBox.addStretch()
        loadVBox.addWidget(b1)
        loadVBox.addWidget(b1Label)
        loadVBox.addStretch()

        cameraHBox = QtGui.QHBoxLayout()
        cameraLabel = QLabel("Recording: ")
        cameraLabel.setFont(self.PicLabelFont)
        cameraLabel.setFixedSize(QSize(120,50))
        cameraOn=QtGui.QRadioButton("  ON")
        cameraOn.setFixedSize(QSize(100,50))
        cameraOn.setStyleSheet("QRadioButton{font: 15pt Ubuntu Mono; border-radius: 10px; font-weight:bold; background-color: #AAAAAA; text-align: center;} QRadioButton::indicator { width: 0px; height: 0px;};")
        cameraOn.clicked.connect(lambda:self.CameraStatus(cameraOn, cameraOff, dataLogOn, dataLogOff))
        cameraOff=QtGui.QRadioButton(" OFF")
        cameraOff.setFixedSize(QSize(100,50))
        cameraOff.setStyleSheet("QRadioButton{font: 15pt Ubuntu Mono; border-radius: 10px; font-weight:bold; background-color: #339999; text-align: center;} QRadioButton::indicator { width: 0px; height: 0px;};")
        cameraOff.clicked.connect(lambda:self.CameraStatus(cameraOff, cameraOn, dataLogOff, dataLogOn))
        cameraHBox.addWidget(cameraLabel)
        cameraHBox.addWidget(cameraOn)
        cameraHBox.addWidget(cameraOff)
        
        dataLogHBox = QtGui.QHBoxLayout()
        dataLogLabel = QLabel("Log Data: ")
        dataLogLabel.setFont(self.PicLabelFont)
        dataLogLabel.setFixedSize(QSize(120,50))
        dataLogOn=QtGui.QRadioButton("  ON")
        dataLogOn.setFixedSize(QSize(100,50))
        dataLogOn.setStyleSheet("QRadioButton{font: 15pt Ubuntu Mono; border-radius: 10px; font-weight:bold; background-color: #AAAAAA; text-align: center;} QRadioButton::indicator { width: 0px; height: 0px;};")
        dataLogOn.clicked.connect(lambda:self.DataLogStatus(dataLogOn, dataLogOff))
        dataLogOff=QtGui.QRadioButton(" OFF")
        dataLogOff.setFixedSize(QSize(100,50))
        dataLogOff.setStyleSheet("QRadioButton{font: 15pt Ubuntu Mono; border-radius: 10px; font-weight:bold; background-color: #339999; text-align: center;} QRadioButton::indicator { width: 0px; height: 0px;};")
        dataLogOff.clicked.connect(lambda:self.DataLogStatus(dataLogOff, dataLogOn))
        dataLogHBox.addWidget(dataLogLabel)
        dataLogHBox.addWidget(dataLogOn)
        dataLogHBox.addWidget(dataLogOff)
        
        printStartHBox = QtGui.QHBoxLayout()
        printStart = QPushButton("Print")
        printStart.setFixedSize(QSize(150,150))
        printStart.setFont(self.MediumLabelFont)
        printStart.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 75;} ")
        #printStart.setStyleSheet("border: 8px solid #339A99; border-radius: 100px; border-style: solid; background : #AAAAAA");
        printStart.clicked.connect(lambda:self.StartPrint())
        printStartHBox.addStretch()
        printStartHBox.addWidget(printStart)
        printStartHBox.addStretch()
        
        printVBox = QtGui.QVBoxLayout()
        printVBox.addLayout(cameraHBox)
        printVBox.addLayout(dataLogHBox)
        printVBox.addStretch()
        printVBox.addStretch()
        printVBox.addStretch()
        printVBox.addLayout(printStartHBox)
        printVBox.addStretch()

        topHBox = QtGui.QHBoxLayout()
        topHBox.addStretch()
        topHBox.addLayout(loadVBox)
        topHBox.addStretch()
        topHBox.addLayout(infoGrid)
        topHBox.addStretch()
        topHBox.addLayout(printVBox)
        topHBox.addStretch()
        
        bottomHBox = QtGui.QHBoxLayout()
        back = QPushButton()
        back.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/back.png")))
        back.setFixedSize(QSize(190,115))
        back.setIconSize(QSize(150,75))
        back.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px} ")
        back.setProperty("ID",10)
        back.setProperty("TO",0)
        back.clicked.connect(lambda:self.GoToPage(back))
        bottomHBox.addStretch()
        bottomHBox.addWidget(back)

        fullVBox = QtGui.QVBoxLayout()
        fullVBox.addStretch()
        fullVBox.addStretch()
        fullVBox.addStretch()
        fullVBox.addLayout(topHBox)
        fullVBox.addStretch()
        fullVBox.addLayout(bottomHBox)

        self.PrintPage = QWidget()
        self.PrintPage.setLayout(fullVBox)
        
    def CreatePrintMonitorPage(self):
        
        self.gCodeFileLabel = QLabel("-")
        self.gCodeFileLabel.setFont(self.PicLabelFont)
        self.gCodeFileLabel.setFixedSize(QSize(500,50))
        self.gCodeFileLabel.setAlignment(QtCore.Qt.AlignCenter)
        
        speedLabel = QLabel("Speed: ")
        speedLabel.setFont(self.PicLabelFont)
        speedLabel.setFixedSize(QSize(100,50))
        self.printMonitorSpeedValue = QLabel(str(self.gCodeFile))
        self.printMonitorSpeedValue.setFont(self.PicLabelFont)
        self.printMonitorSpeedValue.setFixedSize(QSize(300,50))
        
        timeLabel = QLabel("Time: ")
        timeLabel.setFont(self.PicLabelFont)
        timeLabel.setFixedSize(QSize(100,50))
        self.printMonitorTimeValue = QLabel("-")
        self.printMonitorTimeValue.setFont(self.PicLabelFont)
        self.printMonitorTimeValue.setFixedSize(QSize(300,50))
        
        uvLabel = QLabel("UV: ")
        uvLabel.setFont(self.PicLabelFont)
        uvLabel.setFixedSize(QSize(100,50))
        self.printMonitorUVValue = QLabel("-")
        self.printMonitorUVValue.setFont(self.PicLabelFont)
        self.printMonitorUVValue.setFixedSize(QSize(300,50))
        
        needleLabel = QLabel("Needle: ")
        needleLabel.setFont(self.PicLabelFont)
        needleLabel.setFixedSize(QSize(100,50))
        self.printMonitorNeedleValue = QLabel("-")
        self.printMonitorNeedleValue.setFont(self.PicLabelFont)
        self.printMonitorNeedleValue.setFixedSize(QSize(300,50))
        
        materialLabel = QLabel("Material: ")
        materialLabel.setFont(self.PicLabelFont)
        materialLabel.setFixedSize(QSize(100,50))
        self.printMonitorMaterialValue = QLabel("-")
        self.printMonitorMaterialValue.setFont(self.PicLabelFont)
        self.printMonitorMaterialValue.setFixedSize(QSize(300,50))
        
        topHBox = QtGui.QHBoxLayout()
        topHBox.addStretch()
        topHBox.addWidget(self.gCodeFileLabel)
        topHBox.addStretch()
        
        infoGrid = QGridLayout()
        infoGrid.addWidget(speedLabel,0,0)
        infoGrid.addWidget(self.printMonitorSpeedValue,0,1)
        infoGrid.addWidget(timeLabel,1,0)
        infoGrid.addWidget(self.printMonitorTimeValue,1,1)
        infoGrid.addWidget(uvLabel,2,0)
        infoGrid.addWidget(self.printMonitorUVValue,2,1)
        #infoGrid.addWidget(needleLabel,3,0)
        #infoGrid.addWidget(self.printMonitorNeedleValue,3,1)
        #infoGrid.addWidget(materialLabel,4,0)
        #infoGrid.addWidget(self.printMonitorMaterialValue,4,1)
        
        printingTimeLabel = QLabel("Time: ")
        printingTimeLabel.setFont(self.PicLabelFont)
        printingTimeLabel.setFixedSize(QSize(100,50))
        self.printingTimeValue = QLabel("-")
        self.printingTimeValue.setFont(self.PicLabelFont)
        self.printingTimeValue.setFixedSize(QSize(100,50))
        
        layerLabel = QLabel("Layer: ")
        layerLabel.setFont(self.PicLabelFont)
        layerLabel.setFixedSize(QSize(100,50))
        self.layerValue = QLabel("-")
        self.layerValue.setFont(self.PicLabelFont)
        self.layerValue.setFixedSize(QSize(100,50))
        
        printGrid = QGridLayout()
        printGrid.addWidget(printingTimeLabel,0,0)
        printGrid.addWidget(self.printingTimeValue,0,1)
        printGrid.addWidget(layerLabel,1,0)
        printGrid.addWidget(self.layerValue,1,1)
        
        midHBox = QtGui.QHBoxLayout()
        
        midHBox.addStretch()
        midHBox.addLayout(infoGrid)
        midHBox.addStretch()
        midHBox.addLayout(printGrid)

        bottomHBox = QtGui.QHBoxLayout()
        
        pauseButton = QPushButton()
        pauseButton.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/pause.png")))
        pauseButton.setStyleSheet("QPushButton{background:#BBBBBB;}")
        pauseButton.setFixedSize(QSize(100,100))
        pauseButton.setIconSize(QSize(100,100))
        pauseButton.setProperty("STATE", "PAUSE")
        pauseButton.clicked.connect(lambda:self.PausePrint(pauseButton))
        
        back = QPushButton()
        back.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/back.png")))
        back.setFixedSize(QSize(100,100))
        back.setIconSize(QSize(100,100))
        back.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px} ")
        back.setProperty("TO",9)
        back.clicked.connect(lambda:self.StopPrint(pauseButton))
        
        stopButton = QPushButton()
        stopButton.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/stop.png")))
        stopButton.setStyleSheet("QPushButton{background:#BBBBBB;}")
        stopButton.setFixedSize(QSize(100,100))
        stopButton.setIconSize(QSize(100,100))
        stopButton.clicked.connect(lambda:self.StopPrint(stopButton, pauseButton))
        
        showButton = QPushButton()
        showButton.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/Camera.png")))
        showButton.setStyleSheet("QPushButton{background:#BBBBBB;}")
        showButton.setFixedSize(QSize(100,100))
        showButton.setIconSize(QSize(100,100))
        showButton.setProperty("STATE", "SHOW")
        showButton.clicked.connect(lambda:self.ShowCamera(showButton))
        
        
        bottomHBox.addWidget(showButton)
        bottomHBox.addStretch()
        bottomHBox.addStretch()
        bottomHBox.addWidget(pauseButton)
        bottomHBox.addStretch()
        bottomHBox.addStretch()
        bottomHBox.addWidget(stopButton)

        fullVBox = QtGui.QVBoxLayout()
        fullVBox.addLayout(topHBox)
        fullVBox.addStretch()
        fullVBox.addStretch()
        fullVBox.addLayout(midHBox)
        fullVBox.addStretch()
        fullVBox.addLayout(bottomHBox)
        fullVBox.addStretch()
        fullVBox.addWidget(self.pbar)
        fullVBox.addStretch()
        fullVBox.addStretch()

        self.PrintMonitorPage = QWidget()
        self.PrintMonitorPage.setLayout(fullVBox)

    
    def CreatePrintFinishPage(self):
        infoGrid = QGridLayout()
        
        self.printConclusion = QLabel("Print completed Sucessfully")
        self.printConclusion.setFont(self.MediumLabelFont)
        self.printConclusion.setFixedSize(QSize(400,50))
        
        nameLabel = QLabel("Name: ")
        nameLabel.setFont(self.PicLabelFont)
        nameLabel.setFixedSize(QSize(100,50))
        self.nameValue.setFont(self.PicLabelFont)
        self.nameValue.setFixedSize(QSize(150,50))
        
        speedLabel = QLabel("Speed: ")
        speedLabel.setFont(self.PicLabelFont)
        speedLabel.setFixedSize(QSize(100,50))
        self.speedValue.setFont(self.PicLabelFont)
        self.speedValue.setFixedSize(QSize(150,50))
        
        timeLabel = QLabel("Time: ")
        timeLabel.setFont(self.PicLabelFont)
        timeLabel.setFixedSize(QSize(100,50))
        self.timeValue.setFont(self.PicLabelFont)
        self.timeValue.setFixedSize(QSize(150,50))
        
        
        infoGrid.addWidget(nameLabel,0,0)
        infoGrid.addWidget(self.nameValue,0,1)
        infoGrid.addWidget(speedLabel,1,0)
        infoGrid.addWidget(self.speedValue,1,1)
        infoGrid.addWidget(timeLabel,2,0)
        infoGrid.addWidget(self.timeValue,2,1)
        
        star1 = QPushButton()
        star1.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/star.png")))
        star1.setFixedSize(QSize(60,60))
        star1.setIconSize(QSize(40,40))
        star1.setProperty("RATING",1)
        star1.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
        
        star2 = QPushButton()
        star2.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/star.png")))
        star2.setFixedSize(QSize(60,60))
        star2.setIconSize(QSize(40,40))
        star2.setProperty("RATING",2)
        star2.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
        
        star3 = QPushButton()
        star3.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/star.png")))
        star3.setFixedSize(QSize(60,60))
        star3.setIconSize(QSize(40,40))
        star3.setProperty("RATING",3)
        star3.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
        
        star4 = QPushButton()
        star4.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/star.png")))
        star4.setFixedSize(QSize(60,60))
        star4.setIconSize(QSize(40,40))
        star4.setProperty("RATING",4)
        star4.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
        
        star5 = QPushButton()
        star5.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/star.png")))
        star5.setFixedSize(QSize(60,60))
        star5.setIconSize(QSize(40,40))
        star5.setProperty("RATING",5)
        star5.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
        
        star1.clicked.connect(lambda:self.RatePrint(star1,star1,star2,star3,star4,star5))
        star2.clicked.connect(lambda:self.RatePrint(star2,star1,star2,star3,star4,star5))
        star3.clicked.connect(lambda:self.RatePrint(star3,star1,star2,star3,star4,star5))
        star4.clicked.connect(lambda:self.RatePrint(star4,star1,star2,star3,star4,star5))
        star5.clicked.connect(lambda:self.RatePrint(star5,star1,star2,star3,star4,star5))

        rateStarHBox = QtGui.QHBoxLayout()
        rateStarHBox.addWidget(star1)
        rateStarHBox.addWidget(star2)
        rateStarHBox.addWidget(star3)
        rateStarHBox.addWidget(star4)
        rateStarHBox.addWidget(star5)
        
        rateStarLabel = QLabel("Rate your Print")
        rateStarLabel.setFont(self.MediumLabelFont)
        
        rateVBox = QtGui.QVBoxLayout()
        rateVBox.addStretch()
        rateVBox.addWidget(rateStarLabel)
        rateVBox.addLayout(rateStarHBox)
        rateVBox.addStretch()
                
        self.ratingFrame.setLayout(rateVBox)
        self.ratingFrame.hide()
        
        fullRateVBox = QtGui.QVBoxLayout()
        fullRateVBox.addWidget(self.ratingFrame)
        fullRateVBox.addWidget(self.printConclusion)
        
        topHBox = QtGui.QHBoxLayout()
        topHBox.addStretch()
        topHBox.addLayout(fullRateVBox)
        topHBox.addStretch()
        topHBox.addLayout(infoGrid)
        topHBox.addStretch()
        
        bottomHBox = QtGui.QHBoxLayout()
        restart = QPushButton()
        restart.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/restart.png")))
        restart.setFixedSize(QSize(190,115))
        restart.setIconSize(QSize(150,75))
        restart.setStyleSheet("QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px;}")
        restart.setProperty("TO",0)
        restart.clicked.connect(lambda:self.StartPrint())
        
        homePage = QPushButton()
        homePage.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/home.png")))
        homePage.setFixedSize(QSize(190,115))
        homePage.setIconSize(QSize(150,75))
        homePage.setStyleSheet("QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px;}")
        homePage.setProperty("TO",0)
        homePage.clicked.connect(lambda:self.ResetRating(homePage,star1,star2,star3,star4,star5))
        
        back = QPushButton()
        back.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/back.png")))
        back.setFixedSize(QSize(190,115))
        back.setIconSize(QSize(150,75))
        back.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px} ")
        back.setProperty("TO",9)
        back.clicked.connect(lambda:self.ResetRating(back,star1,star2,star3,star4,star5))
        bottomHBox.addStretch()
        bottomHBox.addWidget(restart)
        bottomHBox.addWidget(homePage)
        bottomHBox.addWidget(back)

        fullVBox = QtGui.QVBoxLayout()
        fullVBox.addStretch()
        fullVBox.addLayout(topHBox)
        fullVBox.addStretch()
        fullVBox.addLayout(bottomHBox)
        
        self.PrintFinishPage = QWidget()
        self.PrintFinishPage.setLayout(fullVBox)
    
    def CreateDataInfoPage(self):
        grid = QGridLayout()
        b1 = QPushButton()
        b1.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/Data.png")))
        b1.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 20;} ")
        b1.setFixedSize(QSize(200,200))
        b1.setIconSize(QSize(200,200))
        b1.setProperty("ID",0)
        b1.setProperty("NAME","Data")
        b1.setProperty("TO",14)
        b1.clicked.connect(lambda:self.GoToPage(b1))
        b1Label = QLabel(b1.property("NAME"))
        b1Label.setFont(self.PicLabelFont)

        b2 = QPushButton()
        b2.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/Info.png")))
        b2.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 20;} ")
        b2.setFixedSize(QSize(200,200))
        b2.setIconSize(QSize(200,200))
        b2.setProperty("ID",0)
        b2.setProperty("NAME","Info")
        b2.setProperty("TO",13)
        b2.clicked.connect(lambda:self.GoToPage(b2))
        b2Label = QLabel(b2.property("NAME"))
        b2Label.setFont(self.PicLabelFont)

        grid.addWidget(b1,0,0)
        grid.addWidget(b2,0,1)
        grid.addWidget(b1Label,1,0, Qt.AlignCenter)
        grid.addWidget(b2Label,1,1, Qt.AlignCenter)
        
        bottomHBox = QtGui.QHBoxLayout()
        back = QPushButton()
        back.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/back.png")))
        back.setFixedSize(QSize(190,115))
        back.setIconSize(QSize(150,75))
        back.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px} ")
        back.setProperty("NAME","Back to Main Page")
        back.setProperty("TO",0)
        back.clicked.connect(lambda:self.GoToPage(back))
        bottomHBox.addStretch()
        bottomHBox.addWidget(back)

        fullVBox = QtGui.QVBoxLayout()
        fullVBox.addStretch()
        fullVBox.addStretch()
        fullVBox.addLayout(grid)
        fullVBox.addStretch()
        fullVBox.addLayout(bottomHBox)

        self.DataInfoPage = QWidget()
        self.DataInfoPage.setLayout(fullVBox)

    def CreateDataPage(self):
        
        l1 = QLabel("Name     : Origin")
        l1.setFont(self.SmallLabelFont)
        l2 = QLabel("Size        : 530*480*420 mm")
        l2.setFont(self.SmallLabelFont)
        l3 = QLabel("Weight   : 25 Kg")
        l3.setFont(self.SmallLabelFont)
        l4 = QLabel("Input      : 220V/6A")
        l4.setFont(self.SmallLabelFont)
        l5 = QLabel("Volume   : 130*90*40 mm")
        l5.setFont(self.SmallLabelFont)
        l6 = QLabel("Speed     : 50 m/s")
        l6.setFont(self.SmallLabelFont)
        l7 = QLabel("Pressure: 0.01 - 0.25 MPa")
        l7.setFont(self.SmallLabelFont)
        l8 = QLabel("Disk left: " +str(round(self.diskFree,1)) + "%")
        l8.setFont(self.SmallLabelFont)
        
        infoVBox = QtGui.QVBoxLayout()
        infoVBox.addStretch()
        infoVBox.addWidget(l1)
        infoVBox.addStretch()
        infoVBox.addWidget(l2)
        infoVBox.addStretch()
        infoVBox.addWidget(l3)
        infoVBox.addStretch()
        infoVBox.addWidget(l4)
        infoVBox.addStretch()
        infoVBox.addWidget(l5)
        infoVBox.addStretch()
        infoVBox.addWidget(l6)
        infoVBox.addStretch()
        infoVBox.addWidget(l7)
        infoVBox.addStretch()
        infoVBox.addWidget(l8)
        infoVBox.addStretch()
        
        qrVBox = QtGui.QVBoxLayout()
        qrLabel = QLabel("For Manuals, scan me  ")
        qrLabel.setFont(self.PicLabelFont)
        
        pixmap1 = QtGui.QPixmap()
        pixmap1.load("/home/pi/Tvasta/TouchScreen/Images/handDown.png")
        pixmap1 = pixmap1.scaledToWidth(50)
        handLabel = QLabel()
        handLabel.setPixmap(pixmap1)
        qrLabelHBox = QtGui.QHBoxLayout()
        qrLabelHBox.addWidget(qrLabel)
        qrLabelHBox.addWidget(handLabel)
        
        pixmap = QtGui.QPixmap()
        pixmap.load("/home/pi/Tvasta/TouchScreen/Images/QR.png")
        pixmap = pixmap.scaledToWidth(250)
        label = QLabel()
        label.setPixmap(pixmap)
        
        update = QPushButton("Update")
        update.setFont(self.MediumLabelFont)
        #update.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/back.png")))
        update.setFixedSize(QSize(300,100))
        update.setIconSize(QSize(150,75))
        update.setStyleSheet("QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px;}")
        update.setProperty("NAME","Back to Main Page")
        update.setProperty("TO",12)
        update.clicked.connect(lambda:self.UpdateTouchScreen(back))
        
        qrVBox.addStretch()
        #qrVBox.addLayout(qrLabelHBox)
        qrVBox.addWidget(update)
        qrVBox.addWidget(label)
        qrVBox.addStretch()
        
        dataHBox = QtGui.QHBoxLayout()
        dataHBox.addStretch()
        dataHBox.addLayout(infoVBox)
        dataHBox.addStretch()
        dataHBox.addStretch()
        dataHBox.addStretch()
        dataHBox.addLayout(qrVBox)
        dataHBox.addStretch()

        bottomHBox = QtGui.QHBoxLayout()
        back = QPushButton()
        back.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/back.png")))
        back.setFixedSize(QSize(190,115))
        back.setIconSize(QSize(150,75))
        back.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px} ")
        back.setProperty("NAME","Back to Main Page")
        back.setProperty("TO",12)
        back.clicked.connect(lambda:self.GoToPage(back))
        bottomHBox.addStretch()
        bottomHBox.addWidget(back)

        fullVBox = QtGui.QVBoxLayout()
        fullVBox.addLayout(dataHBox)
        fullVBox.addLayout(bottomHBox)

        self.DataPage = QWidget()
        self.DataPage.setLayout(fullVBox)

    def CreateDataRetrievePage(self):
        label = QLabel("  Select Log files to Copy / Delete")
        label.setFont(self.MediumLabelFont)
        self.listDataLog = QListWidget()
        dl = os.listdir("/home/pi/DataLog")
        dl.sort()
        dlabel = dl;
        
        for item in os.listdir("/media/pi"):
            #print(item)
            if os.path.ismount(os.path.join("/media/pi",item)):
                self.mountedDevice = os.path.join("/media/pi",item)
                break

        self.listDataLog.setStyleSheet("QListWidget{font-family: Ubuntu Mono;  font-weight:bold;  font-size: 25pt; color: #000000 ; margin : 0 22px 0 22px} QListWidget::item:selected{ color : #000000; background : #339A99} QScrollBar:vertical{border:2px solid #AAAAAA; background: #339A99; width : 50px;}");
        
        for d in dl:
            item = QListWidgetItem(d)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Unchecked)
            item.setBackground(QColor("#AAAAAA"))
            self.listDataLog.addItem(item)
            
        self.listDataLog.clicked.connect(lambda : self.DataSelected(self.listDataLog))
        
        topHBox = QtGui.QVBoxLayout()
        topHBox.addWidget(label)
        topHBox.addWidget(self.listDataLog)
        #topHBox.addStretch()
        
        bottomHBox = QtGui.QHBoxLayout()
        move = QPushButton()
        move.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/storage.png")))
        move.setFixedSize(QSize(150,115))
        move.setIconSize(QSize(150,75))
        move.setStyleSheet("QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px;}")
        move.clicked.connect(lambda:self.MoveDataLog())
        
        refresh = QPushButton()
        refresh.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/refresh.png")))
        refresh.setFixedSize(QSize(150,115))
        refresh.setIconSize(QSize(150,75))
        refresh.setStyleSheet("QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px;}")
        refresh.clicked.connect(lambda:self.RefreshDataLog())
        
        delete = QPushButton()
        delete.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/delete.png")))
        delete.setFixedSize(QSize(150,115))
        delete.setIconSize(QSize(150,75))
        delete.setStyleSheet("QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px;}")
        delete.clicked.connect(lambda:self.DeleteDataLog())
        
        back = QPushButton()
        back.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/back.png")))
        back.setFixedSize(QSize(150,115))
        back.setIconSize(QSize(150,75))
        back.setStyleSheet("QPushButton:pressed  {background : #339A99} QPushButton{background : #AAAAAA; border-radius : 10; margin: 20px} ")
        back.setProperty("NAME","Back to Data and Info Page")
        back.setProperty("TO",12)
        back.clicked.connect(lambda:self.GoToPage(back))
        bottomHBox.addWidget(delete)
        bottomHBox.addStretch()
        bottomHBox.addWidget(move)
        bottomHBox.addWidget(refresh)
        bottomHBox.addWidget(back)

        fullVBox = QtGui.QVBoxLayout()
        fullVBox.addLayout(topHBox)
        fullVBox.addLayout(bottomHBox)
        
        self.DataRetrievePage = QWidget()
        self.DataRetrievePage.setLayout(fullVBox)
        
    def CreateLoadFilePage(self):
        label = QLabel("  Select G-Code file to Print")
        label.setFont(self.MediumLabelFont)
        self.listFile = QListWidget()
        df = []
        for item in os.listdir("/media/pi"):
            #print(item)
            if os.path.ismount(os.path.join("/media/pi",item)):
                self.mountedDevice = os.path.join("/media/pi",item)
                self.currentDirectory = self.mountedDevice
                df = os.listdir(self.currentDirectory)
                break

        self.listFile.setStyleSheet("QListWidget{font-family: Ubuntu Mono;  font-weight:bold;  font-size: 25pt; color: #000000 ; margin : 0 22px 0 22px} QListWidget::item:selected{ color : #000000; background : #339A99} QScrollBar:vertical{border:2px solid #AAAAAA; background: #339A99; width : 50px;}");
        
        self.listFile.clear()
        fDir = QtGui.QFont()
        fDir.setPointSize(25)
        fDir.setFamily("Ubunto Mono")
        fDir.setBold(True)
        fFile = QtGui.QFont()
        fFile.setPointSize(25)
        fFile.setFamily("Ubunto Mono")
        fFile.setBold(False)
        df.sort()
        for d in df:
            if not isfile(join(self.currentDirectory, d)):
                item = QListWidgetItem(d)
                item.setBackground(QColor("#BBBBBB"))
                item.setFont(fDir)
                self.listFile.addItem(item)
        for f in df:
            if isfile(join(self.currentDirectory, f)) and ".gcode" in f:
                item = QListWidgetItem(f)
                item.setBackground(QColor("#AAAAAA"))
                item.setFont(fFile)
                self.listFile.addItem(item)
            
        
        topHBox = QtGui.QVBoxLayout()
        topHBox.addWidget(label)
        topHBox.addWidget(self.listFile)
        #topHBox.addStretch()
        
        bottomHBox = QtGui.QHBoxLayout()
        
        enter = QPushButton("Enter")
        enter.setFixedSize(QSize(150,115))
        enter.setProperty("STATE", "NONE")
        enter.setStyleSheet("QPushButton:pressed{background : #339A99} QPushButton{margin: 20px; color : #000000; font-size:40px; font-weight : bold; background : #AAAAAA; border-radius : 10;}")
        enter.clicked.connect(lambda:self.NavigateFront(enter))
        
        back = QPushButton("Back")
        back.setFixedSize(QSize(150,115))
        back.setProperty("STATE", "NONE")
        back.setStyleSheet("QPushButton:pressed{background : #339A99} QPushButton{margin: 20px; color : #000000; font-size:40px; font-weight : bold; background : #AAAAAA; border-radius : 10;}")
        back.clicked.connect(lambda:self.NavigateBack(back))
        
        close = QPushButton("Close")
        close.setFixedSize(QSize(150,115))
        close.setStyleSheet("QPushButton:pressed{background : #339A99} QPushButton{margin: 20px; color : #000000; font-size:40px; font-weight : bold; background : #AAAAAA; border-radius : 10;}")
        close.setProperty("NAME","Back to Print Page")
        close.setProperty("TO",9)
        close.clicked.connect(lambda:self.GoToPage(close))
        
        self.listFile.clicked.connect(lambda : self.FileSelected(self.listFile, enter, back))
        
        bottomHBox.addStretch()
        bottomHBox.addWidget(enter)
        bottomHBox.addWidget(back)
        bottomHBox.addWidget(close)

        fullVBox = QtGui.QVBoxLayout()
        fullVBox.addLayout(topHBox)
        fullVBox.addLayout(bottomHBox)
        
        self.LoadFilePage = QWidget()
        self.LoadFilePage.setLayout(fullVBox)
        
        
    def MoveByChanged(self, b):
        if(b.property("ID") == "Z"):
            a = b.text();
            a = float(a)*10
            if(a > 10):
                a=0.01
            b.setText(str(a));
        if(b.property("ID") == "XY"):
            a = b.text();
            a = float(a)*10
            if(a > 10):
                a=0.1
            b.setText(str(a));
            
    def HomeCommand(self, b):
        print("home_enter")    
        if("X" in b.property("NAME")):
            print("x_enter")
            self.xPos = self.xHomePosition
            self.xPosValue.setText(str(self.xPos))
            self.serialThreadMKS.serialOut("G28 X0\n");
        elif("Y" in b.property("NAME")):
            self.yPos = self.yHomePosition
            self.yPosValue.setText(str(self.yPos))
            self.serialThreadMKS.serialOut("G28 Y0\n");
        elif("Z" in b.property("NAME")):
            self.zPos = self.zHomePosition
            self.zPosValue.setText(str(self.zPos))
            self.serialThreadMKS.serialOut("G28 Z0\n");
        elif("All" in b.property("NAME")):
            self.zPos = self.zHomePosition
            self.zPosValue.setText(str(self.zPos))
            self.serialThreadMKS.serialOut("G28 Z0\n");
            self.yPos = self.yHomePosition
            self.yPosValue.setText(str(self.yPos))
            self.serialThreadMKS.serialOut("G28 Y0\n");
            self.xPos = self.xHomePosition
            self.xPosValue.setText(str(self.xPos))
            self.serialThreadMKS.serialOut("G28 X0\n");
        print("home_exit")
           
    def HighLightHome(self,b):
        b.setStyleSheet("background: #339A99; border: 8px solid #339A99; border-radius: 40px; border-style: solid;");
        
    def UnHighLightHome(self,b):
        b.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 40px; border-style: solid;");
        
    def HighLightCircle(self,b):
        b.setStyleSheet("background: #339A99; border: 8px solid #339A99; border-radius: 40px; border-style: solid;");
        
    def UnHighLightCircle(self,b):
        b.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 40px; border-style: solid;");
       
    def HighLightCalibration(self,b,bLabel):
        b.setStyleSheet("background-color: #339A99; border: 8px solid #339A99; border-radius: 75px; border-style: solid;");
        
    def UnHighLightCalibration(self,b,bLabel):
        b.setStyleSheet("background-color: #AAAAAA; border: 8px solid #339A99; border-radius: 75px; border-style: solid;");
         
    def HighLightNumber(self,b):
        b.setStyleSheet("background: #ED9D61; border: 8px solid #ED9D61; border-radius: 40px; border-style: solid;");
        
    def UnHighLightNumber(self,b):
        b.setStyleSheet("background: #AAAAAA; border: 8px solid #ED9D61; border-radius: 40px; border-style: solid;");
          
    def HighLightRectangle(self,b):
        b.setStyleSheet("background-color: #339A99; border: 8px solid #339A99;  border-radius: 10px;");
        
    def UnHighLightRectangle(self,b):
        b.setStyleSheet("background-color: #AAAAAA; border: 8px solid #339A99;  border-radius: 10px;");
        
    def Translate(self, b):
        if("X" in b.property("NAME")):
            self.xPos = round(self.xPos + (b.property("DIRECTION") * float(self.xyMoveBy.text())),2)
            if(self.xPos > 225):
                self.xPos = 225
            elif(self.xPos < 0):
                self.xPos = 0
            self.xPosValue.setText(str(self.xPos))
            self.serialThreadMKS.serialOut("G0 X" + str(self.xPos) + " F1200;\n");
        elif("Y" in b.property("NAME")):
            self.yPos = round(self.yPos + (b.property("DIRECTION") * float(self.xyMoveBy.text())),2)
            if(self.yPos > self.yHomePosition):
                self.yPos = self.yHomePosition
            elif(self.yPos < 0):
                self.yPos = 0
            self.yPosValue.setText(str(self.yPos))
            self.serialThreadMKS.serialOut("G0 Y" + str(self.yPos) + " F1200;\n");
        elif("Z" in b.property("NAME")):
            self.zPos = round(self.zPos + (b.property("DIRECTION") * float(self.zMoveBy.text())),2)
            if(self.zPos > self.zHomePosition):
                self.zPos = self.zHomePosition
            elif(self.zPos < 0):
                self.zPos = 0
            self.zPosValue.setText(str(self.zPos))
            self.serialThreadMKS.serialOut("G0 Z" + str(self.zPos) + " F600;\n");
            
            
    def UpdateTouchScreen(self,b):
        self.mountedDevice = "";
        for item in os.listdir("/media/pi"):
            if os.path.ismount(os.path.join("/media/pi",item)):
                self.mountedDevice = os.path.join("/media/pi",item)
                break
        if(self.mountedDevice == ""):
            msgBox = QMessageBox()
            msgBox.setText("Make sure the pendrive is inserted properly before trying to update.")
            msgBox.setWindowFlags(~QtCore.Qt.WindowCloseButtonHint)
            msgBox.setStyleSheet("QMessageBox{ border: 4px solid #339A99; background: #BBBBBB; font-family: Ubuntu Mono;  font-weight:bold;  font-size: 25pt; color: #000000 ; } QPushButton{width:150px; height:75px; border: 2px solid #339A99; border-radius :10px; font-family: Ubuntu Mono; font-weight:bold; background: #AAAAAA; font-size: 25pt; color: #000000 ;} QPushButton:pressed{background : #339A99}");
            msgBox.move(100,100)
            msgBox.exec_()
            return
        else:
            encryptedFile = ""
            for item in os.listdir(self.mountedDevice):
                #print(item)
                if item == "AvayTouchScreenUpdate.py":
                    encryptedFile = os.path.join(self.mountedDevice,item)
                    print(encryptedFile)
                    break
            
            if(encryptedFile == ""):
                msgBox = QMessageBox()
                msgBox.setText("Make sure the update file is present in the home folder of pendrive.")
                msgBox.setWindowFlags(~QtCore.Qt.WindowCloseButtonHint)
                msgBox.setStyleSheet("QMessageBox{ border: 4px solid #339A99; background: #BBBBBB; font-family: Ubuntu Mono;  font-weight:bold;  font-size: 25pt; color: #000000 ; } QPushButton{width:150px; height:75px; border: 2px solid #339A99; border-radius :10px; font-family: Ubuntu Mono; font-weight:bold; background: #AAAAAA; font-size: 25pt; color: #000000 ;} QPushButton:pressed{background : #339A99}");
                msgBox.move(100,100)
                msgBox.exec_()
                return
                
            msgBox = QMessageBox()
            msgBox.setText("Are you sure you want to update the TouchScreen ?")
            msgBox.setWindowFlags(~QtCore.Qt.WindowCloseButtonHint)
            msgBox.setStandardButtons( QMessageBox.Cancel | QMessageBox.Ok )
            msgBox.setStyleSheet("QMessageBox{ border: 4px solid #339A99; background: #BBBBBB; font-family: Ubuntu Mono;  font-weight:bold;  font-size: 25pt; color: #000000 ; } QPushButton{width:150px; height:75px; border: 2px solid #339A99; border-radius :10px; font-family: Ubuntu Mono; font-weight:bold; background: #AAAAAA; font-size: 25pt; color: #000000 ;} QPushButton:pressed{background : #339A99}");
            msgBox.move(100,100)
            r = msgBox.exec_()
            if r == 0x00000400:
                f = Fernet(self.decryptionKey)
                with open(encryptedFile, "rb") as file:
                    # read the encrypted data
                    encrypted_data = file.read()
                # decrypt data
                decrypted_data = f.decrypt(encrypted_data)
                # write the original file
                with open(self.TouchScreenFileName, "wb") as file:
                    file.write(decrypted_data)  
                   
                msgBox = QMessageBox()
                msgBox.setText("The update was Successful. Do you want to restart now ?")
                msgBox.setWindowFlags(~QtCore.Qt.WindowCloseButtonHint)
                msgBox.setStandardButtons( QMessageBox.Cancel | QMessageBox.Ok )
                msgBox.setStyleSheet("QMessageBox{ border: 4px solid #339A99; background: #BBBBBB; font-family: Ubuntu Mono;  font-weight:bold;  font-size: 25pt; color: #000000 ; } QPushButton{width:150px; height:75px; border: 2px solid #339A99; border-radius :10px; font-family: Ubuntu Mono; font-weight:bold; background: #AAAAAA; font-size: 25pt; color: #000000 ;} QPushButton:pressed{background : #339A99}");
                msgBox.move(100,100)
                r = msgBox.exec_()
                if r == 0x00000400:
                    command = "/usr/bin/sudo /sbin/shutdown -r now"
                    import subprocess
                    process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
                    output = process.communicate()[0]
                    
    def ExtruderOn(self, b):
        if(b.property("NAME") == "ATRIUM"):
            self.serialThreadMKS.serialOut("M106 P1 S255\n");
            b.setStyleSheet("border: 10px solid #339A99; border-radius: 40px; border-style: solid; background : #339A99");
        elif(b.property("NAME") == "VENTRICLE"):
            self.serialThreadMKS.serialOut("M106 P0 S255\n");
            b.setStyleSheet("border: 10px solid #339A99; border-radius: 40px; border-style: solid; background : #339A99");
            
    def ExtruderOff(self, b):
        if(b.property("NAME") == "ATRIUM"):
            self.serialThreadMKS.serialOut("M106 P1 S0\n");
            b.setStyleSheet("border: 8px solid #339A99; border-radius: 40px; border-style: solid; background : #AAAAAA");
        elif(b.property("NAME") == "VENTRICLE"):
            self.serialThreadMKS.serialOut("M106 P0 S0\n");
            b.setStyleSheet("border: 8px solid #339A99; border-radius: 40px; border-style: solid; background : #AAAAAA");
        
    def ChooseExtruder(self, b):
        if(b.property("STATE") == "ATRIUM"):
            self.serialThreadMKS.serialOut("M280 P0 S" + str(self.serialThreadMKS.atriumServoPos) + " ;\n");
            b.setStyleSheet("border: 7px solid #ED9D61; border-radius: 40px; border-style: solid; background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,stop: 1.0 #AAAAAA, stop: 0.51 #AAAAAA, stop: 0.49 #339A99, stop: 0 #339A99);");
            b.setProperty("STATE", "VENTRICLE")
        elif(b.property("STATE") == "VENTRICLE"):
            self.serialThreadMKS.serialOut("M280 P0 S" + str(self.serialThreadMKS.ventricleServoPos) + ";\n");
            b.setProperty("STATE", "ATRIUM")
            b.setStyleSheet("border: 7px solid #ED9D61; border-radius: 40px; border-style: solid; background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,stop: 0 #AAAAAA, stop: 0.49 #AAAAAA, stop: 0.51 #339A99, stop: 1.0 #339A99);");
    
    def ChangeOffset(self,b,bLabel,bSign,b1,b2,b3,b4):
        value = int(b1.text())*1000 + int(b2.text()) * 100 +  int(b3.text()) * 10 +  int(b4.text())
        if(bSign.text() == "-"):
            value *= -1
        value += bLabel.property("MULTIPLIER") * b.property("DIRECTION") 
        p = value
        if(p < 0):
            bSign.setText("-")
            p *= -1
        else:
            bSign.setText(" ")
        if(p >= 10000):
            return
        b4.setText(str(int(p%10)))
        p /= 10
        b3.setText(str(int(p%10)))
        p /= 10
        b2.setText(str(int(p%10)))
        p /= 10
        b1.setText(str(int(p%10)))
        
    def SetOffset(self,bSign,b1,b2,b3,b4):
        if(b1.property("NAME") == "X"):
            self.xOffset = float(b1.text())*10 + float(b2.text()) +  float(b3.text())/10 +  float(b4.text())/100
            if(bSign.text() == "-"):
                self.xOffset *= -1
            self.xOffsetButton.setText(str(self.xOffset))
            self.stack.setCurrentIndex(b1.property("TO"))
        elif(b1.property("NAME") == "Y"):
            self.yOffset = float(b1.text())*10 + float(b2.text()) +  float(b3.text())/10 +  float(b4.text())/100
            if(bSign.text() == "-"):
                self.yOffset *= -1
            self.yOffsetButton.setText(str(self.yOffset))
            self.stack.setCurrentIndex(b1.property("TO"))
        elif(b1.property("NAME") == "Z1"):
            self.z1Offset = float(b1.text())*10 + float(b2.text()) +  float(b3.text())/10 +  float(b4.text())/100
            if(bSign.text() == "-"):
                self.z1Offset *= -1
            self.z1OffsetButton.setText(str(self.z1Offset))
            self.stack.setCurrentIndex(b1.property("TO"))
        elif(b1.property("NAME") == "Z2"):
            self.z2Offset = float(b1.text())*10 + float(b2.text()) +  float(b3.text())/10 +  float(b4.text())/100
            if(bSign.text() == "-"):
                self.z2Offset *= -1
            self.z2OffsetButton.setText(str(self.z2Offset))
            self.stack.setCurrentIndex(b1.property("TO"))
        
        f = open('/home/pi/Tvasta/TouchScreen/settings.txt', "w")
        f.write("Xoffset " + str(self.xOffset) + "\n")
        f.write("Yoffset " + str(self.yOffset) + "\n")
        f.write("Z1offset " + str(self.z1Offset) + "\n")
        f.write("Z2offset " + str(self.z2Offset) + "\n")
        f.write("AtriumHeight " + str(self.atriumHeight) + "\n")
        f.write("VentricleHeight " + str(self.ventricleHeight) + "\n")
        f.close()
    
    def ResetEditPage(self,b,bSign,b1,b2,b3,b4):
        if(b.property("ID") == "X"):
                
             if(self.xOffset < 0 ):
                 bSign.setText("-")
             else:
                 bSign.setText(" ")
                 
             p = int(abs(round(self.xOffset,2) * 100))
             b4.setText(str(int(p%10)))   
             p /= 10
             b3.setText(str(int(p%10)))   
             p /= 10
             b2.setText(str(int(p%10)))   
             p /= 10
             b1.setText(str(int(p%10)))
        elif(b.property("ID") == "Y"):
                
             if(self.yOffset < 0 ):
                 bSign.setText("-")
             else:
                 bSign.setText(" ")
                 
             p = int(abs(round(self.yOffset,2) * 100))
             b4.setText(str(int(p%10)))   
             p /= 10
             b3.setText(str(int(p%10)))   
             p /= 10
             b2.setText(str(int(p%10)))   
             p /= 10
             b1.setText(str(int(p%10)))
        elif(b.property("ID") == "Z1"):
                
             if(self.z1Offset < 0 ):
                 bSign.setText("-")
             else:
                 bSign.setText(" ")
                 
             p = int(abs(round(self.z1Offset,2) * 100))
             b4.setText(str(int(p%10)))   
             p /= 10
             b3.setText(str(int(p%10)))   
             p /= 10
             b2.setText(str(int(p%10)))   
             p /= 10
             b1.setText(str(int(p%10)))
        elif(b.property("ID") == "Z2"):
                
             if(self.z2Offset < 0 ):
                 bSign.setText("-")
             else:
                 bSign.setText(" ")
                 
             p = int(abs(round(self.z2Offset,2) * 100))
             b4.setText(str(int(p%10)))   
             p /= 10
             b3.setText(str(int(p%10)))   
             p /= 10
             b2.setText(str(int(p%10)))   
             p /= 10
             b1.setText(str(int(p%10)))
        self.stack.setCurrentIndex(b.property("TO"))
        
    def Curing(self,b):
        if(b.property("NAME") == "ATRIUM"):
            if(b.property("STATE") == "OFF"):
                self.serialThreadMKS.serialOut("M42 P59 S255\n");
                b.setStyleSheet("border: 8px solid #339A99; border-radius: 100px; border-style: solid; background : #339A99");
                b.setProperty("STATE", "ON")
            else:
                self.serialThreadMKS.serialOut("M42 P59 S0\n");
                b.setStyleSheet("border: 8px solid #339A99; border-radius: 100px; border-style: solid; background : #AAAAAA");
                b.setProperty("STATE", "OFF")
        
        elif(b.property("NAME") == "VENTRICLE"):
            if(b.property("STATE") == "OFF"):
                self.serialThreadMKS.serialOut("M42 P63 S255\n");
                b.setStyleSheet("border: 8px solid #339A99; border-radius: 100px; border-style: solid; background : #339A99");
                b.setProperty("STATE", "ON")
            else:
                self.serialThreadMKS.serialOut("M42 P63 S0\n");
                b.setStyleSheet("border: 8px solid #339A99; border-radius: 100px; border-style: solid; background : #AAAAAA");
                b.setProperty("STATE", "OFF")
       
       
    def CuringIntensity(self,b,bLabel):
        bLabel.setText(str(b.value()))
        
    def CenterZ(self,b):
        if(b.property("EXTRUDER") == "ATRIUM"):
            self.serialThreadMKS.serialOut("G28 Z0\n");
            self.serialThreadMKS.serialOut("G28 Y0\n");
            self.serialThreadMKS.serialOut("G28 X0\n");
            self.serialThreadMKS.serialOut("G28 X0\n");
            self.serialThreadMKS.serialOut("M280 P0 S" + str(self.serialThreadMKS.atriumServoPos) + " ;\n");
            self.serialThreadMKS.serialOut("G92 Z" + str(self.zHomePosition - (self.z1Offset + self.atriumHeight)) + ";\n");
            self.serialThreadMKS.serialOut("G92 X" + str(self.xHomePosition - self.xOffset) + ";\n");
            self.serialThreadMKS.serialOut("G92 Y" + str(self.yHomePosition - self.yOffset) + ";\n");
            self.serialThreadMKS.serialOut("G0 X" +str(self.centerX) + " Y" + str(self.centerY) + " F2400;\n");
            self.serialThreadMKS.serialOut("G0 Z0 F1200;\n");
        elif(b.property("EXTRUDER") == "VENTRICLE"):
            self.serialThreadMKS.serialOut("G28 Z0\n");
            self.serialThreadMKS.serialOut("G28 Y0\n");
            self.serialThreadMKS.serialOut("G28 X0\n");
            self.serialThreadMKS.serialOut("G28 X0\n");
            self.serialThreadMKS.serialOut("M280 P0 S" + str(self.serialThreadMKS.ventricleServoPos) + " ;\n");
            self.serialThreadMKS.serialOut("G92 Z" + str(self.zHomePosition - (self.z2Offset + self.ventricleHeight)) + ";\n");
            self.serialThreadMKS.serialOut("G92 X" + str(self.xHomePosition - self.xOffset) + ";\n");
            self.serialThreadMKS.serialOut("G92 Y" + str(self.yHomePosition - self.yOffset) + ";\n");
            self.serialThreadMKS.serialOut("G0 X" +str(self.centerX - self.extruderOffsetX) + " Y" + str(self.centerY - self.extruderOffsetY) + " F2400;\n");
            self.serialThreadMKS.serialOut("G0 Z0 F1200;\n");
            
        
                    
    def CalibrateNeedle(self,b):
        if(b.property("NAME") == "ATRIUM"):
            if(b.text() == "Find"):
                self.atriumCalibrate.setText("Stop")
                self.ventricleCalibrate.setText("Find")
                self.calibrationTitle.setText("Calibrating Please Wait .. ")
                
                #self.serialThreadMKS.serialMKS = serial.Serial(self.serialThreadMKS.portname, self.serialThreadMKS.baudrate,timeout=0.08)
                self.serialThreadMKS.buffer = 1;
                self.serialThreadMKS.aStartZ =35
                self.serialThreadMKS.needleSensing = "ATRIUM_HOME"
            elif(b.text() == "Stop"):
                b.setText("Find")
                self.calibrationTitle.setText("Calibration Stopped")
                self.serialThreadMKS.needleSensing = "NONE"  
                
        elif(b.property("NAME") == "VENTRICLE"):
            if(b.text() == "Find"):            
                self.atriumCalibrate.setText("Find")
                self.ventricleCalibrate.setText("Stop")
                b.setText("Stop")
                self.calibrationTitle.setText("Calibrating Please Wait .. ")
                #self.serialThreadMKS.serialMKS = serial.Serial(self.serialThreadMKS.portname, self.serialThreadMKS.baudrate,timeout=0.08)
                self.serialThreadMKS.buffer = 1;
                self.serialThreadMKS.vStartZ = 35
                self.serialThreadMKS.needleSensing = "VENTRICLE_HOME"  
            elif(b.text() == "Stop"):
                b.setText("Find")
                self.calibrationTitle.setText("Calibration Stopped")
                self.serialThreadMKS.needleSensing = "NONE"   
        return
        
    def SetNeedleHeight(self,mv,v):
        if(mv.text() == "-"):
            return
            
        if(mv.property("NAME") == "ATRIUM"):
            self.atriumHeight = float(mv.text())
        elif(mv.property("NAME") == "VENTRICLE"):
            self.ventricleHeight = float(mv.text())
        v.setText(mv.text())
        mv.setText("-")
        
        f = open('/home/pi/Tvasta/TouchScreen/settings.txt', "w")
        f.write("Xoffset " + str(self.xOffset) + "\n")
        f.write("Yoffset " + str(self.yOffset) + "\n")
        f.write("Z1offset " + str(self.z1Offset) + "\n")
        f.write("Z2offset " + str(self.z2Offset) + "\n")
        f.write("AtriumHeight " + str(self.atriumHeight) + "\n")
        f.write("VentricleHeight " + str(self.ventricleHeight) + "\n")
        f.close()
    
    def LoadFile(self,name,speed,time,uv,needle,material,pressure):
        dialog = QFileDialog(self,'GCode Files', "/media/pi", "gcode(*.gcode)")
        dialog.directoryEntered.connect(lambda:self.DirectoryChanged(dialog))
        dialog.fileSelected.connect(lambda:self.FileOpened(dialog,name,speed,time,uv,needle,material,pressure))
        dialog.setStyleSheet(" QPushButton{width:200px; height:100px; font-family: Ubuntu Mono;  font-weight:bold;  font-size: 25pt; color: #000000 ;} font-family: Ubuntu Mono;  font-size: 25pt; color: #000000 ; QLabel{font-family: Ubuntu Mono;  font-size: 25pt; color: #000000 ;}");
        
        dialog.showFullScreen()
    
    def DirectoryChanged(self,b):
        path = str(b.directory().absolutePath())
        if("/media/pi" not in path):
            b.setDirectory("/media/pi")


    def CameraStatus(self, b1,b2,b3,b4):
        if("ON" in b1.text()):
            self.dataLog = True
            self.ratingFrame.show()
            b3.setStyleSheet("QRadioButton{font: 15pt Ubuntu Mono; border-radius: 10px; font-weight:bold; background-color: #339999;} QRadioButton::indicator { width: 0px; height: 0px;};")
            b4.setStyleSheet("QRadioButton{font: 15pt Ubuntu Mono; border-radius: 10px; font-weight:bold; background-color: #AAAAAA;} QRadioButton::indicator { width: 0px; height: 0px;};")
            self.serialThreadMKS.recording = True
            b1.setStyleSheet("QRadioButton{font: 15pt Ubuntu Mono; border-radius: 10px; font-weight:bold; background-color: #339999;} QRadioButton::indicator { width: 0px; height: 0px;};")
            b2.setStyleSheet("QRadioButton{font: 15pt Ubuntu Mono; border-radius: 10px; font-weight:bold; background-color: #AAAAAA;} QRadioButton::indicator { width: 0px; height: 0px;};")
        else:
            self.serialThreadMKS.recording = False
            b1.setStyleSheet("QRadioButton{font: 15pt Ubuntu Mono; border-radius: 10px; font-weight:bold; background-color: #339999;} QRadioButton::indicator { width: 0px; height: 0px;};")
            b2.setStyleSheet("QRadioButton{font: 15pt Ubuntu Mono; border-radius: 10px; font-weight:bold; background-color: #AAAAAA;} QRadioButton::indicator { width: 0px; height: 0px;};")
    

    def DataLogStatus(self, b1,b2):
        if("ON" in b1.text()):
            self.dataLog = True
            self.ratingFrame.show()
            b1.setStyleSheet("QRadioButton{font: 15pt Ubuntu Mono; border-radius: 10px; font-weight:bold; background-color: #339999;} QRadioButton::indicator { width: 0px; height: 0px;};")
            b2.setStyleSheet("QRadioButton{font: 15pt Ubuntu Mono; border-radius: 10px; font-weight:bold; background-color: #AAAAAA;} QRadioButton::indicator { width: 0px; height: 0px;};")
        else:
            self.dataLog = False
            self.ratingFrame.hide()
            b1.setStyleSheet("QRadioButton{font: 15pt Ubuntu Mono; border-radius: 10px; font-weight:bold; background-color: #339999;} QRadioButton::indicator { width: 0px; height: 0px;};")
            b2.setStyleSheet("QRadioButton{font: 15pt Ubuntu Mono; border-radius: 10px; font-weight:bold; background-color: #AAAAAA;} QRadioButton::indicator { width: 0px; height: 0px;};")
    
    def StartPrint(self):
        if(not path.exists(self.gCodeFile)):
            msgBox = QMessageBox()
            msgBox.setText("Load a Gcode File before Printing.")
            msgBox.setWindowFlags(~QtCore.Qt.WindowCloseButtonHint)
            msgBox.setStyleSheet("QMessageBox{background: #AAAAAA; border: 4px; border-radius : 20px; font-family: Ubuntu Mono;  font-weight:bold;  font-size: 25pt; color: #000000 ; } QPushButton{width:100px; height:50px; font-family: Ubuntu Mono;  font-weight:bold;  font-size: 25pt; color: #000000 ;}");
            msgBox.move(100,100)
            msgBox.exec_()
            return
    
        self.pbar.setValue(0)
        #self.cameraThread = CameraThread()   # Start thread
        #self.cameraThread.start()
        self.serialThreadMKS.gcodeName = self.gCodeFile.split('/')[-1].split('.')[0]

        printHistoryFile = open("/home/pi/DataLog/printHistory.txt", 'a')
        printHistoryFile.write("File Name : " + self.printNameValue.text() + "\n")
        printHistoryFile.write("Print Speed : " + self.printSpeedValue.text() + "\n")
        printHistoryFile.write("Print Time : " + self.printTimeValue.text() + " min"+"\n")
        printHistoryFile.write("UV : " + self.printUVValue.text() + "\n")
        printHistoryFile.write("Material : " + self.printMaterialValue.text() + "\n")
        printHistoryFile.write("Pressure : " + self.printPressureValue.text() + "\n")
        printHistoryFile.write("Needle : " + self.printNeedleValue.text() + "\n")
        printHistoryFile.write("Date and Time : " + str(datetime.now().strftime("%d/%m/%Y %H:%M:%S")) + "\n\n")
        printHistoryFile.close()
            
        if(self.dataLog == True):
            ls = os.listdir("/home/pi/DataLog")
            nameAvailable = False
            newName = self.serialThreadMKS.gcodeName
            i = 1
            while nameAvailable == False:
                nameAvailable = True
                for l in ls:
                    if(newName == l):
                        nameAvailable = False
                        newName = self.serialThreadMKS.gcodeName + "_" + str(i)
                        break;
                i = i+1
                        
            self.serialThreadMKS.directory = "/home/pi/DataLog/" + newName
            os.mkdir(self.serialThreadMKS.directory)
            logFile = open(self.serialThreadMKS.directory + "/log.txt", 'w')
            logFile.write("File Name : " + self.printNameValue.text() + "\n")
            logFile.write("Print Speed : " + self.printSpeedValue.text() + "\n")
            logFile.write("Print Time : " + self.printTimeValue.text() + "\n")
            logFile.write("UV : " + self.printUVValue.text() + "\n")
            logFile.write("Material : " + self.printMaterialValue.text() + "\n")
            logFile.write("Pressure : " + self.printPressureValue.text() + "\n")
            logFile.write("Needle : " + self.printNeedleValue.text() + "\n")
            logFile.close()
            
        self.serialThreadMKS.cameraNeeded = True
        self.serialThreadMKS.showCamera = True
        self.serialThreadMKS.firstTime = True
        self.serialThreadMKS.firstTimePreview = False
        self.startTime = time.time()
        
        self.stack.setCurrentIndex(10)
        self.gCodeFileLabel.setText(self.serialThreadMKS.gcodeName)
        
        self.serialThreadMKS.serialMKS = serial.Serial(self.serialThreadMKS.portname, self.serialThreadMKS.baudrate,timeout=0.2)
        self.serialThreadMKS.buffer = 1;
        self.nameValue.setText(self.serialThreadMKS.gcodeName)
        self.speedValue.setText(self.speed)
        self.timeValue.setText(self.time)
        self.serialThreadMKS.acknowledged = 0
        while(len(self.serialThreadMKS.txq) or self.serialThreadMKS.acknowledged  > 0):
            pass
        self.txq=[]
        self.serialThreadMKS.serialOut("G28 Z0;\n");
        self.serialThreadMKS.serialOut("G28 Y0;\n");
        self.serialThreadMKS.serialOut("G28 X0;\n");
        
        #self.serialThreadMKS.serialOut("G92 X93 Y149;\n");
        self.serialThreadMKS.serialOut("G1 Z50 F600;\n");
        #print(self.z1Offset)
        #print(self.atriumHeight)
        self.serialThreadMKS.serialOut("G92 Z" + str(50 - (self.atriumHeight + self.z1Offset)) + ";\n");
        self.serialThreadMKS.serialOut("G92 X" + str(self.xHomePosition - self.xOffset) + ";\n");
        self.serialThreadMKS.serialOut("G92 Y" + str(self.yHomePosition - self.yOffset) + ";\n");
        
        self.serialThreadMKS.extruderType = 1 
        self.serialThreadMKS.avDiff = round(self.z2Offset + self.ventricleHeight - self.needleSensorToBed - (self.z1Offset + self.atriumHeight - self.needleSensorToBed),2)
        
        f = open(self.gCodeFile, "r")
        f1 = f.readlines()
        f.close()
        self.totalGcodeLine = len(f1)
        for l in f1:
            if(not l.isspace() and l[0] != ';'):
                self.serialThreadMKS.serialOut(l);
        self.printPaused = False
        self.printStarted = True
        print(self.serialThreadMKS.acknowledged)
        
    def ShowCamera(self,b):
        self.serialThreadMKS.showCamera = not self.serialThreadMKS.showCamera;
        self.serialThreadMKS.firstTimePreview = True
        
    def PausePrint(self,b):
        if(b.property("STATE") == "PAUSE"):
            print("Print paused")
            b.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/Resume.png")))
            self.printPaused = True
            self.txq = self.serialThreadMKS.txq
            self.serialThreadMKS.txq = []
            self.serialThreadMKS.acknowledged = 0
            if(self.serialThreadMKS.extruderType == 1):
                self.serialThreadMKS.serialOut("M106 P1 S0\n")
            elif(self.serialThreadMKS.extruderType == 2):
                self.serialThreadMKS.serialOut("M106 P0 S0\n")
            b.setProperty("STATE", "RESUME")
        elif(b.property("STATE") == "RESUME"):
            print("Print Resumed")
            b.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/pause.png")))
            if(self.serialThreadMKS.extruderType == 1):
                self.txq.insert(0,"M106 P1 S255\n")
            elif(self.serialThreadMKS.extruderType == 2):
                self.txq.insert(0,"M106 P0 S255\n")
            self.serialThreadMKS.txq = self.txq
            self.txq = []
            self.printPaused = False
            b.setProperty("STATE", "PAUSE")
        
    def Reconnect(self):
        self.serialThreadMKS.txq = []
        self.serialThreadMKS.serialMKS.write("M112;\n".encode())
        self.serialThreadMKS.serialMKS.close()
        time.sleep(1)
        self.serialThreadMKS = SerialThreadMKS("/dev/ttyUSB0", 250000)   # Start serial thread
        self.serialThreadMKS.start()
            
    def StopPrint(self,b,b1):
        #b.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/pause.png")))
        print(str(self.totalGcodeLine))
        print(str(len(self.serialThreadMKS.txq)))
        print(str(len(self.txq)))
        self.printConclusion.setText("Print Stopped at " + 
                str(int((self.totalGcodeLine - 
                (len(self.serialThreadMKS.txq) + len(self.txq))
                ) * 100 /self.totalGcodeLine)) + " %.")
        self.printStarted = False
        self.serialThreadMKS.cameraNeeded = False
        self.serialThreadMKS.txq = []
        self.serialThreadMKS.serialMKS.write("M112;\n".encode())
        self.serialThreadMKS.serialMKS.close()
        time.sleep(1)
        self.serialThreadMKS = SerialThreadMKS("/dev/ttyUSB0", 250000)   # Start serial thread
        self.serialThreadMKS.start()
        b1.setIcon(QIcon(QPixmap("/home/pi/Tvasta/TouchScreen/Images/pause.png")))
        b1.setProperty("STATE", "PAUSE")
        self.stack.setCurrentIndex(11)
        time.sleep(1)
        self.serialThreadMKS.serialOut("G28 Z0;\n");
        self.serialThreadMKS.serialOut("G28 Y0;\n");
        self.serialThreadMKS.serialOut("G28 X0;\n");
        
        
        
    def RatePrint(self,b,b1,b2,b3,b4,b5):
        if(b.property("RATING") == 1):
            b1.setStyleSheet("background: #339A99; border: 8px solid #000000; border-radius: 25px; border-style: solid;");
            b2.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
            b3.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
            b4.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
            b5.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
            self.printRating = 1
        elif(b.property("RATING") == 2):
            b1.setStyleSheet("background: #339A99; border: 8px solid #000000; border-radius: 25px; border-style: solid;");
            b2.setStyleSheet("background: #339A99; border: 8px solid #000000; border-radius: 25px; border-style: solid;");
            b3.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
            b4.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
            b5.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
            self.printRating = 2
        elif(b.property("RATING") == 3):
            b1.setStyleSheet("background: #339A99; border: 8px solid #000000; border-radius: 25px; border-style: solid;");
            b2.setStyleSheet("background: #339A99; border: 8px solid #000000; border-radius: 25px; border-style: solid;");
            b3.setStyleSheet("background: #339A99; border: 8px solid #000000; border-radius: 25px; border-style: solid;");
            b4.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
            b5.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
            self.printRating = 3
        elif(b.property("RATING") == 4):
            b1.setStyleSheet("background: #339A99; border: 8px solid #000000; border-radius: 25px; border-style: solid;");
            b2.setStyleSheet("background: #339A99; border: 8px solid #000000; border-radius: 25px; border-style: solid;");
            b3.setStyleSheet("background: #339A99; border: 8px solid #000000; border-radius: 25px; border-style: solid;");
            b4.setStyleSheet("background: #339A99; border: 8px solid #000000; border-radius: 25px; border-style: solid;");
            b5.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
            self.printRating = 4
        elif(b.property("RATING") == 5):
            b1.setStyleSheet("background: #339A99; border: 8px solid #000000; border-radius: 25px; border-style: solid;");
            b2.setStyleSheet("background: #339A99; border: 8px solid #000000; border-radius: 25px; border-style: solid;");
            b3.setStyleSheet("background: #339A99; border: 8px solid #000000; border-radius: 25px; border-style: solid;");
            b4.setStyleSheet("background: #339A99; border: 8px solid #000000; border-radius: 25px; border-style: solid;");
            b5.setStyleSheet("background: #339A99; border: 8px solid #000000; border-radius: 25px; border-style: solid;");
            self.printRating = 5
                    
    def ResetRating(self,b,b1,b2,b3,b4,b5):
        b1.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
        b2.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
        b3.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
        b4.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
        b5.setStyleSheet("background: #AAAAAA; border: 8px solid #339A99; border-radius: 25px; border-style: solid;");
        self.printRating = 0
        self.stack.setCurrentIndex(b.property("TO"))
        
    def DataSelected(self,b):
        if(b.currentItem().checkState() == Qt.Unchecked):
            b.currentItem().setCheckState(Qt.Checked)
            b.currentItem().setBackground(QColor("#339A99"))
            self.listDataLog.setStyleSheet("QListWidget{font-family: Ubuntu Mono;  font-weight:bold;  font-size: 25pt; color: #000000 ;  margin : 0 22px 0 22px; } QListWidget::item:selected{ color : #000000; background : #339A99} QScrollBar:vertical{border:2px solid #AAAAAA; background: #339A99; width : 50px;}");
        
        elif(b.currentItem().checkState() == Qt.Checked):
            b.currentItem().setCheckState(Qt.Unchecked)
            b.currentItem().setBackground(QColor("#AAAAAA"))
            self.listDataLog.setStyleSheet("QListWidget{font-family: Ubuntu Mono;  font-weight:bold;  font-size: 25pt; color: #000000 ;  margin : 0 22px 0 22px; } QListWidget::item:selected{ color : #000000; background : #AAAAAA} QScrollBar:vertical{border:2px solid #AAAAAA; background: #339A99; width : 50px;}");
        
    def RefreshDataLog(self):
        self.listDataLog.clear()
        dl = os.listdir("/home/pi/DataLog")
        dl.sort()
        self.listDataLog.setStyleSheet("QListWidget{font-family: Ubuntu Mono; margin : 0 22px 0 22px; font-weight:bold;  font-size: 25pt; color: #000000 ;} QListWidget::item:selected{ color : #000000}");
        
        for d in dl:
            item = QListWidgetItem(d)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Unchecked)
            item.setBackground(QColor("#AAAAAA"))
            self.listDataLog.addItem(item)
            
    def DeleteDataLog(self):
        msgBox = QMessageBox()
        msgBox.setText("Are you sure you want to delete the selected files ?")
        msgBox.setWindowFlags(~QtCore.Qt.WindowCloseButtonHint)
        msgBox.setStandardButtons( QMessageBox.Cancel | QMessageBox.Ok )
        msgBox.setStyleSheet("QMessageBox{ border: 4px solid #339A99; background: #BBBBBB; font-family: Ubuntu Mono;  font-weight:bold;  font-size: 25pt; color: #000000 ; } QPushButton{width:150px; height:75px; border: 2px solid #339A99; border-radius :10px; font-family: Ubuntu Mono; font-weight:bold; background: #AAAAAA; font-size: 25pt; color: #000000 ;} QPushButton:pressed{background : #339A99}");
        msgBox.move(100,100)
        r = msgBox.exec_()
        if r == 0x00400000:
            return
        for i in range(self.listDataLog.count()):
            if(self.listDataLog.item(i).checkState() == Qt.Checked):
                shutil.rmtree(os.path.join("/home/pi/DataLog",self.listDataLog.item(i).text()))
                #print(self.listDataLog.item(i).text())
                
        self.listDataLog.clear()
        dl = os.listdir("/home/pi/DataLog")
        dl.sort()
        i = 0
        self.listDataLog.setStyleSheet("QListWidget{font-family: Ubuntu Mono;  margin : 0 22px 0 22px;  font-weight:bold;  font-size: 25pt; color: #000000 ;} QListWidget::item:selected{ color : #000000}");
        
        for d in dl:
            item = QListWidgetItem(d)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Unchecked)
            item.setBackground(QColor("#AAAAAA"))
            self.listDataLog.addItem(item)
        
                
    def MoveDataLog(self):
        self.mountedDevice = "";
        for item in os.listdir("/media/pi"):
            #print(item)
            if os.path.ismount(os.path.join("/media/pi",item)):
                self.mountedDevice = os.path.join("/media/pi",item)
                break
        if(self.mountedDevice == ""):
            msgBox = QMessageBox()
            msgBox.setText("Make sure the pendrive is inserted properly before moving Log data.")
            msgBox.setWindowFlags(~QtCore.Qt.WindowCloseButtonHint)
            msgBox.setStyleSheet("QMessageBox{ border: 4px solid #339A99; background: #BBBBBB; font-family: Ubuntu Mono;  font-weight:bold;  font-size: 25pt; color: #000000 ; } QPushButton{width:150px; height:75px; border: 2px solid #339A99; border-radius :10px; font-family: Ubuntu Mono; font-weight:bold; background: #AAAAAA; font-size: 25pt; color: #000000 ;} QPushButton:pressed{background : #339A99}");
            msgBox.move(100,100)
            msgBox.exec_()
            return
        else:
            msgBox = QMessageBox()
            msgBox.setText("Are you sure you want to move the selected files to storage device ?")
            msgBox.setWindowFlags(~QtCore.Qt.WindowCloseButtonHint)
            msgBox.setStandardButtons( QMessageBox.Cancel | QMessageBox.Ok )
            msgBox.setStyleSheet("QMessageBox{ border: 4px solid #339A99; background: #BBBBBB; font-family: Ubuntu Mono;  font-weight:bold;  font-size: 25pt; color: #000000 ; } QPushButton{width:150px; height:75px; border: 2px solid #339A99; border-radius :10px; font-family: Ubuntu Mono; font-weight:bold; background: #AAAAAA; font-size: 25pt; color: #000000 ;} QPushButton:pressed{background : #339A99}");
            msgBox.move(100,100)
            r = msgBox.exec_()
            if r == 0x00000400:
                for i in range(self.listDataLog.count()):
                    if(self.listDataLog.item(i).checkState() == Qt.Checked):
                        shutil.move(os.path.join("/home/pi/DataLog",self.listDataLog.item(i).text()), os.path.join(self.mountedDevice,self.listDataLog.item(i).text() ))
                
                self.listDataLog.clear()
                dl = os.listdir("/home/pi/DataLog")
                dl.sort()
                self.listDataLog.setStyleSheet("QListWidget{font-family: Ubuntu Mono;  font-weight:bold;  font-size: 25pt; margin : 0 22px 0 22px; color: #000000 ;} QListWidget::item:selected{ color : #000000}");
                
                for d in dl:
                    item = QListWidgetItem(d)
                    item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                    item.setCheckState(QtCore.Qt.Unchecked)
                    item.setBackground(QColor("#AAAAAA"))
                    self.listDataLog.addItem(item)
        self.stack.setCurrentIndex(b.property("TO"))
        
    def FileSelected(self,b, b1, b2):
        if not isfile(join(self.currentDirectory, b.currentItem().text())):
            b1.setProperty("STATE", "DIR")
            b2.setProperty("STATE", "DIR")
            b1.setText("Enter")
        else:
            b1.setProperty("STATE", "FILE")
            b2.setProperty("STATE", "FILE")
            b1.setText("Open")
            self.gCodeFile = join(self.currentDirectory, b.currentItem().text())
            self.FileOpened()
            
    def NavigateFront(self,b):
        if(b.property("STATE") == "DIR"):
            if isfile(join(self.mountedDevice, self.listFile.currentItem().text())):
                return
            b.setProperty("STATE", "NONE")
            self.currentDirectory = join(self.currentDirectory, self.listFile.currentItem().text())
            df = os.listdir(self.currentDirectory)
            self.listFile.clear()
            fDir = QtGui.QFont()
            fDir.setPointSize(25)
            fDir.setFamily("Ubunto Mono")
            fDir.setBold(True)
            fFile = QtGui.QFont()
            fFile.setPointSize(25)
            fFile.setFamily("Ubunto Mono")
            fFile.setBold(False)
            df.sort()
            for d in df:
                if not isfile(join(self.currentDirectory, d)):
                    item = QListWidgetItem(d)
                    item.setBackground(QColor("#BBBBBB"))
                    item.setFont(fDir)
                    self.listFile.addItem(item)
            for f in df:
                if isfile(join(self.currentDirectory, f)) and ".gcode" in f:
                    item = QListWidgetItem(f)
                    item.setBackground(QColor("#AAAAAA"))
                    item.setFont(fFile)
                    self.listFile.addItem(item)
            b.property("STATE") == "NONE"
        elif(b.property("STATE") == "FILE"):
            p = self.gCodeFile.split('/')
            l = len(p)
            name = p[l-1]
            msgBox = QMessageBox()
            msgBox.setText("Are you sure, you want to load " + str(name) + " ?")
            msgBox.setWindowFlags(~QtCore.Qt.WindowCloseButtonHint)
            msgBox.setStandardButtons( QMessageBox.Cancel | QMessageBox.Ok )
            msgBox.setStyleSheet("QMessageBox{ border: 4px solid #339A99; font-family: Ubuntu Mono;  font-weight:bold;  font-size: 25pt; color: #000000; background: #BBBBBB;  } QPushButton{width:150px; height:75px; border: 2px solid #339A99; border-radius :10px; font-family: Ubuntu Mono; font-weight:bold; background: #AAAAAA; font-size: 25pt; color: #000000 ;} QPushButton:pressed{background : #339A99}");
            msgBox.move(100,100)
            r = msgBox.exec_()
            if r == 0x00400000:
                return
            self.stack.setCurrentWidget(self.PrintPage)
        
    def NavigateBack(self,b):
        b.setProperty("STATE", "NONE")
        path = Path(self.currentDirectory)
        if(str(path.parent) == "/media/pi"):
            return
        self.currentDirectory = path.parent
        df = os.listdir(self.currentDirectory)
        self.listFile.clear()
        fDir = QtGui.QFont()
        fDir.setPointSize(25)
        fDir.setFamily("Ubunto Mono")
        fDir.setBold(True)
        fFile = QtGui.QFont()
        fFile.setPointSize(25)
        fFile.setFamily("Ubunto Mono")
        fFile.setBold(False)
        df.sort()
        for d in df:
            if not isfile(join(self.currentDirectory, d)):
                item = QListWidgetItem(d)
                item.setBackground(QColor("#BBBBBB"))
                item.setFont(fDir)
                self.listFile.addItem(item)
        for f in df:
            if isfile(join(self.currentDirectory, f)) and ".gcode" in f:
                item = QListWidgetItem(f)
                item.setBackground(QColor("#AAAAAA"))
                item.setFont(fFile)
                self.listFile.addItem(item)

        
    def LoadFileClicked(self,b):
        #print("load file")
        if(self.diskFree < 2):
            msgBox = QMessageBox()
            msgBox.setText("Low memory. Please Copy/Delete the data log files !!!")
            msgBox.setWindowFlags(~QtCore.Qt.WindowCloseButtonHint)
            msgBox.setStandardButtons( QMessageBox.Ok )
            msgBox.setStyleSheet("QMessageBox{ border: 4px solid #339A99; background: #BBBBBB; font-family: Ubuntu Mono;  font-weight:bold;  font-size: 25pt; color: #000000 ; } QPushButton{width:150px; height:75px; border: 2px solid #339A99; border-radius :10px; font-family: Ubuntu Mono; font-weight:bold; background: #AAAAAA; font-size: 25pt; color: #000000 ;} QPushButton:pressed{background : #339A99}");
            msgBox.move(100,100)
            r = msgBox.exec_()
            return
        df = []
        for item in os.listdir("/media/pi"):
            print(item)
            if os.path.ismount(os.path.join("/media/pi",item)):
                self.mountedDevice = os.path.join("/media/pi",item)
                self.currentDirectory = self.mountedDevice
                df = os.listdir(self.mountedDevice)
                break
        print(df)
        if(len(df) == 0):
            msgBox = QMessageBox()
            msgBox.setText("Make sure the pendrive is inserted properly before trying to load file.")
            msgBox.setWindowFlags(~QtCore.Qt.WindowCloseButtonHint)
            msgBox.setStyleSheet("QMessageBox{ border: 4px solid #339A99; background: #BBBBBB; font-family: Ubuntu Mono;  font-weight:bold;  font-size: 25pt; color: #000000 ; } QPushButton{width:150px; height:75px; border: 2px solid #339A99; border-radius :10px; font-family: Ubuntu Mono; font-weight:bold; background: #AAAAAA; font-size: 25pt; color: #000000 ;} QPushButton:pressed{background : #339A99}");
            msgBox.move(100,100)
            msgBox.exec_()
            return
        else:            
            self.listFile.clear()
            fDir = QtGui.QFont()
            fDir.setPointSize(25)
            fDir.setFamily("Ubunto Mono")
            fDir.setBold(True)
            fFile = QtGui.QFont()
            fFile.setPointSize(25)
            fFile.setFamily("Ubunto Mono")
            fFile.setBold(False)
            df.sort()
            for d in df:
                if not isfile(join(self.mountedDevice, d)):
                    item = QListWidgetItem(d)
                    item.setBackground(QColor("#AAAAAA"))
                    item.setFont(fDir)
                    self.listFile.addItem(item)
            #print(self.listFile)
            for f in df:
                if isfile(join(self.mountedDevice, f)) and ".gcode" in f:
                    item = QListWidgetItem(f)
                    item.setBackground(QColor("#AAAAAA"))
                    item.setFont(fFile)
                    self.listFile.addItem(item)
            print(self.listFile)
            self.stack.setCurrentIndex(b.property("TO"))
    
    def FileOpened(self):
        p = self.gCodeFile.split('/')
        l = len(p)
        self.printNameValue.setText(p[l-1])
        name = p[l-1]
        f = open(self.gCodeFile, "r")
        fLines = f.readlines()
        for l in fLines:
            if("ENDREGION" in l):
                break
            w = l.split(':')
            if(w[0] == "SPEED"):
                self.printSpeedValue.setText(w[1])
                self.printMonitorSpeedValue.setText(w[1])
                self.speed = w[1]
            elif(w[0] == "TIME"):
                self.printTimeValue.setText(w[1]+" min")
                self.printMonitorTimeValue.setText(w[1]+" min")
                self.time = w[1]
            elif(w[0] == "CURING"):
                print(str(w[1]))
                self.printUVValue.setText(str(w[1]))
                self.printMonitorUVValue.setText(str(w[1]))
            elif(w[0] == "NEEDLEGAUGE"):
                self.printNeedleValue.setText(w[1])
                self.printMonitorNeedleValue.setText(w[1])
            elif(w[0] == "MATERIAL"):
                self.printMaterialValue.setText(w[1])
                self.printMonitorMaterialValue.setText(w[1])
            elif(w[0] == "PRESSURE"):
                self.printPressureValue.setText(w[1])
            elif(w[0] == "LAYERHEIGHT"):
                self.layerHeight = float(w[1])
        
                    
    def GoToPage(self,b):
        self.stack.setCurrentIndex(b.property("TO"))
    
    def ShowPrintingTime(self,sec):
        m = sec // 60
        sec = sec % 60
        h = m // 60
        m = m % 60
        self.printingTimeValue.setText("{0}:{1}:{2}".format(int(h),int(m),int(sec)))
        
        
    def TimerTick(self):
        
        #if(self.serialThreadMKS.acknowledged != 0 and (datetime.now() - self.serialThreadMKS.time).total_seconds() > 2.5):
            #print("I did it")
        #    self.serialThreadMKS.time = datetime.now()
        #    self.serialThreadMKS.acknowledged = self.serialThreadMKS.acknowledged - 1
        if(self.serialThreadMKS.needleSensing == "READYA"):
            self.atriumMeasuredValueLabel.setText(str(round(self.serialThreadMKS.aStartZ - self.needleSensorToBed,1)))
            self.serialThreadMKS.needleSensing = "NONE"
            self.atriumCalibrate.setText("Find")
            self.calibrationTitle.setText("Calibration Done")
        elif(self.serialThreadMKS.needleSensing == "READYV"):
            self.ventricleMeasuredValueLabel.setText(str(round(self.serialThreadMKS.vStartZ- self.needleSensorToBed,1)))
            self.ventricleCalibrate.setText("Find")
            self.serialThreadMKS.needleSensing = "NONE"
            self.calibrationTitle.setText("Calibration Done")
        elif("ATRIUM" in self.serialThreadMKS.needleSensing ):
            self.zPos = self.serialThreadMKS.aStartZ
            self.zPosValue.setText(str(self.zPos))
            self.yPos = self.serialThreadMKS.aStartY
            self.yPosValue.setText(str(self.yPos))
            self.xPos = self.serialThreadMKS.aStartX
            self.xPosValue.setText(str(self.xPos))
        elif("VENTRICLE" in self.serialThreadMKS.needleSensing):
            self.zPos = self.serialThreadMKS.vStartZ
            self.zPosValue.setText(str(self.zPos))
            self.yPos = self.serialThreadMKS.vStartY
            self.yPosValue.setText(str(self.yPos))
            self.xPos = self.serialThreadMKS.vStartX
            self.xPosValue.setText(str(self.xPos))
            
        if(self.printStarted == True and self.printPaused == False):
            val = int((self.totalGcodeLine - len(self.serialThreadMKS.txq)) * 100 /self.totalGcodeLine)
            self.pbar.setValue(val)
            currentTime = time.time()
            self.ShowPrintingTime(currentTime - self.startTime)
            if(self.layerHeight != 0 and self.serialThreadMKS.zPos != 30):
                self.layerValue.setText(str(round(self.serialThreadMKS.zPos / self.layerHeight)))
                
            if(len(self.serialThreadMKS.txq) == 0):
                self.printStarted = False
                self.serialThreadMKS.cameraNeeded = False
                self.printConclusion.setText("Print completed successfully")
                self.stack.setCurrentIndex(11)


def main():
    #app = QApplication(sys.argv)
    ex = OriginTouchScreen()
    sys.exit(app.exec_())
	
if __name__ == '__main__':
    main()
