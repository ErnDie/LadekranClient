#! /usr/bin/env python3
import socket
import string
import time
from paho.mqtt import client as mqtt_client

import ntplib
from datetime import datetime, timedelta

# server_address = ('arduinoerdie.hopto.org', 80)
server_address = ('192.168.2.199', 80)

broker = 'test.mosquitto.org'
port = 1883
topicLedOn = "arduinolederdieon"
topicLedOff = "arduinolederdieoff"
topicResults = "arduinolederdieresults"
received_payload = ""

def TCPRequest(message: string):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(server_address)
        s.sendall(bytes(message, 'utf-8'))
        data = s.recv(1024).decode()
        s.close()

    return data


def UDPRequest(message: string):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Data to send
        messagebytes = bytes(message, 'utf-8')
        # Send the message to the server
        sock.sendto(messagebytes, server_address)
        # Receive the response from the server (optional)
        data, server = sock.recvfrom(1024)
        data_decoded = data.decode()
        print('Received:', data)
        return data
    finally:
        # Close the socket
        sock.close()

def MQTTRequest(response: ntplib.NTPStats):
    startTime = datetime.utcfromtimestamp(datetime.now().timestamp() + response.offset)
    print(startTime.strftime("%H:%M:%S.%f"))
    start_time = datetime.now()
    client = connect_mqtt()
    client.loop_start()
    subscribe(client, topicResults)
    publish(client, topicLedOn)
    time.sleep(3)
    client.loop_stop()
    end_time = datetime.now()
    rttTimeDelta = end_time - start_time

    responseParts = received_payload.split(';')
    ntpDelayString = responseParts[0].split("NTP-Delay: ")[1]
    serverTimeString = responseParts[1].split("UTC-Time: ")[1]
    serverTime = datetime.strptime(serverTimeString, "%H:%M:%S.%f")

    delayTimeDelta = serverTime - startTime
    microSeconds = str(delayTimeDelta).split('.')

    owd = float(str(delayTimeDelta.seconds) + "." + microSeconds[1])
    rtt = getRTT(rttTimeDelta, ntpDelayString)
    print("TCP OWD: " + str(owd) + "s")
    print("TCP RTT: " + str(rtt) + "s")

def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)

    client = mqtt_client.Client()
    # client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(broker, port)
    return client


def publish(client, topic: string):

    time.sleep(1)
    msg = "led=on"
    result = client.publish(topic, msg)
    status = result[0]
    if status == 0:
        print(f"Send `{msg}` to topic `{topic}`")
    else:
        print(f"Failed to send message to topic {topic}")


def subscribe(client: mqtt_client, topic: string):
    def on_message(client, userdata, msg):
        print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")
        global received_payload
        received_payload = msg.payload.decode()
    client.subscribe(topic)
    client.on_message = on_message


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
    else:
         print("Failed to connect, return code %d\n", rc)


def getRTT(timeDelta: timedelta, ntpDelayString: string):
    ntpDelay = int(ntpDelayString)
    timeDelta = timeDelta - timedelta(microseconds=ntpDelay * 1000)
    # If you use timedelta.microseconds the 0 at the beginning will be cut
    microSecondsString = str(timeDelta).split('.')[1]
    rtt = float(str(timeDelta.seconds) + "." + microSecondsString)
    return rtt

