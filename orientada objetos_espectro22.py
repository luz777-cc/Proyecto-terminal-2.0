import ssl
import sys
import random
import time
import serial
import numpy as np
import matplotlib.pyplot as plt
from scipy import io
from scipy.fft import fft, fftfreq, fftshift
from scipy.signal import butter, filtfilt
from paho.mqtt import client as mqtt_client
from datetime import datetime
import paho.mqtt.client as paho

buffer = 512

# hcitool scan
# sdptool records 24:71:89:EC:69:DC
# sudo rfcomm bind 0 24:71:89:EC:69:DC 1

import paho.mqtt.client

class Conectar():
    
    def __init__(self):
        
        self.broker = 'broker.hivemq.com' #'broker.emqx.io' #148.206.49.17'
        self.port = 1883
        self.client = paho.mqtt.client.Client(client_id='luz-subsIoT', clean_session=False)
        self.topic_entrada = "eegIoT/data/frecuencias"
        self.topic = "eegIoT/data"
        self.topicFilt = "eegIoT/data/Filtro"
        self.topicFFilt = "eegIoT/data/PSD"
        self.topicMarcas = "eegIoT/data/Marcas"
        self.topicPSDRaw = "eegIoT/data/PSDRaw"
        self.username = 'eegIoT'
        self.password = '1234'
        self.dt1 = datetime.now()
        self.dt2 = datetime.now()
        self.a = 0
        self.a1 = 'false'
        self.a2 = [12, 30]
        self.SYNC = 0xAA
        self.EXCODE = 0x55
        self.CODES = {0x02: 'POOR_SIGNAL',
                 0x04: 'ATTENTION',
                 0x05: 'MEDITATION',
                 0x16: 'BLINK',
                 0x80: 'RAW',
                 0x83: 'ASIC_EEG_POWER'}

        self.time = list(range(buffer))
        self.data = [0]*buffer
        self.dataFilt = [0]*buffer
        self.dataFFilt = [0]*buffer
        self.dataPSDRaw = [0]*buffer
        self.contador = 0
        
    def on_connect(self, client, userdata, flags, rc):
        print('MM connected (%s)' % client._client_id)
        self.client.subscribe(self.topic_entrada, qos=0)
    
    def on_publish(self, client, userdata, result):
        pass
        
    def on_message(self, client, userdata, message):
        print('------------------------------')
        self.a = message.payload.decode()
        print(type(self.a), self.a)
        if self.a == 'true' or self.a == 'false':
            self.a1 = self.a
        elif len(self.a.split(' ')) == 2:
            self.a2 = self.a.split(' ')
        else:
            print("dato erroneo")
            
    def parse(self, payload):
        payload_parser_state = 'new_data_row'
        for byte in payload:
            count = 1
            if payload_parser_state == 'new_data_row':
                if byte == self.EXCODE:
                    nex = 1
                    payload_parser_state = 'excode'
                else:
                    code = byte
                    payload_parser_state = 'decoded'
            elif payload_parser_state == 'excode':
                if byte == self.EXCODE:
                    nex += 1
                    payload_parser_state = 'excode'
                else:
                    code = byte
                    payload_parser_state = 'decoded'
            elif payload_parser_state == 'decoded':
                if code < 0x80:
                    value = byte
                    #print('{}: {}'.format(CODES[code], value))
                    if self.CODES[code] == 'POOR_SIGNAL' and value > 0:
                        #print('mala señal')
                        n=0
                        #client.publish(topic, 'mala señal')
                    payload_parser_state = 'new_data_row'
                else:
                    vlength = byte
                    values = []
                    payload_parser_state = 'multiple'
            elif payload_parser_state == 'multiple':
                if vlength > 0:
                    values.append(byte)
                    vlength -= 1
                    if vlength > 0:
                        payload_parser_state = 'multiple'
                    else:
                        if self.CODES[code] == 'RAW':
                            value = values[0] * 256 + values[1]
                            if value > 32767:
                                value -= 65536
                            self.data = self.data[1:] + [value]
                            
                            #filtro
                            
                            ws = 512
                            ent = float(self.a2[0])
                            sal = float(self.a2[1])
                            low = (2*ent)/ws
                            high = (2*sal)/ws
                            NOrden = 4
                            
                            #b, a= butter(NOrden,[low,high],'bandpass')
                            b, a= butter(NOrden,[ent,sal], fs =ws, btype ='band')
                            self.dataFilt = list(filtfilt(b, a, self.data))
                            self.dt2 = datetime.now()
                            
                            #self.dataFFilt = list(fftfreq(self.dataFilt))
                            yf= fft(self.dataFilt)
                            yplot = fftshift(yf)
                            yplot = (1.0/buffer) * np.abs(yplot)
                            self.dataFFilt = list(yplot)
                            
                            yf1= fft(self.data)
                            yplot1 = fftshift(yf1)
                            yplot1 = (1.0/buffer) * np.abs(yplot1)
                            self.dataPSDRaw = list(yplot1)
                            
                            #print(self.dataFFilt, type(self.dataFFilt), len(self.dataFFilt))
                            
                            if self.a1 == 'true':
                                self.contador = self.contador + 1
                                fichero = open('./texto.txt', 'a', encoding ='utf-8')
                                fichero.write(str(self.contador)+('.- ')+str(self.dt2)+(' ')+str(self.data)+('\n'))
                                marcas = (str(self.contador)+('.- ')+str(self.dt2)+(' ')+str(self.data)+('\n'))
                                self.client.publish(self.topicMarcas, str(marcas))
                                self.dt2 = datetime.now()
                                diferencia = (self.dt2-self.dt1)
                                total_s = diferencia.total_seconds()
                                if total_s >= 0.25:
                                    self.dt1 = datetime.now()
                                    self.client.publish(self.topic, str(self.data))
                                    self.client.publish(self.topicFilt, str(self.dataFilt))
                                    self.client.publish(self.topicFFilt, str(self.dataFFilt))
                                    self.client.publish(self.topicPSDRaw, str(self.dataPSDRaw))
                                    
                                    
                            diferencia = (self.dt2-self.dt1)
                            total_s = diferencia.total_seconds()
                            if total_s >= 0.25:
                                self.dt1 = datetime.now()
                                self.client.publish(self.topic, str(self.data))
                                self.client.publish(self.topicFilt, str(self.dataFilt))
                                self.client.publish(self.topicFFilt, str(self.dataFFilt))
                                self.client.publish(self.topicPSDRaw, str(self.dataPSDRaw))
                                
                                    
                        if self.CODES[code] == 'ASIC_EEG_POWER':
                            value = []
                            for i in range(0,24,3):
                                value.append(values[i]+values[i+1]*256+values[i+2]*256*256)
                            total = sum(value)
                            if total > 0:
                                value = [v/total for v in value]
                                #print('rBP: {}'.format(value))
                        payload_parser_state = 'new_data_row'
                        
                        if self.CODES[code] == 'BLINK':
                            print('parpadeando')
                        if self.CODES[code] == 'ATTENTION':
                            print('Atencion')
                        if self.CODES[code] == 'MEDITATION':
                            print('Meditación')

    def run(self):
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish
        self.client.connect(self.broker, self.port)
        self.client.loop_start()   
    
        inp = serial.Serial('/dev/rfcomm0', baudrate=57600)
        parser_state = 'idle'

        with inp:
            while(1):
                byte = int.from_bytes(inp.read(), byteorder='little', signed=False)
                if byte == self.SYNC and parser_state == 'idle':
                    parser_state = 'sync01'
                elif byte == self.SYNC and parser_state == 'sync01':
                    parser_state = 'sync02'
                elif byte == self.SYNC and parser_state == 'sync02':
                    parser_state = 'sync02'
                elif byte > self.SYNC and parser_state == 'sync02':
                    parser_state = 'idle'
                elif byte < self.SYNC and parser_state == 'sync02':
                    count = byte
                    self.payload = []
                    checksum = 0
                    parser_state = 'packet'
                elif parser_state == 'packet' and count > 0:
                    count -= 1
                    self.payload.append(byte)
                    checksum += byte
                elif parser_state == 'packet' and count == 0:
                    if (checksum & 0xFF) ^ 0xFF == byte:
                        self.parse(self.payload)
                    else:
                        print('packet con error')
                    parser_state = 'idle'

if __name__ == '__main__':
    fichero = open('texto.txt', 'w')
    fichero.write(' ')
    fichero.close()
    Conectar().run()