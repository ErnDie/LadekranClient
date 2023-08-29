#! /usr/bin/env python3

import json

from crosslab.soa_services.file import FileService__Consumer, FileServiceEvent, FileService__Producer
from crosslab.soa_services.webcam import WebcamService__Producer, GstTrack

import arduino_connection
import asyncio
import serial

from crosslab.api_client import APIClient
from crosslab.soa_client.device_handler import DeviceHandler
from crosslab.soa_services.message import MessageServiceEvent
from crosslab.soa_services.message import MessageService__Producer, MessageService__Consumer

ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)


async def main_async():
    # read config from file
    with open("config.json", "r") as configfile:
        conf = json.load(configfile)

    # debug; delete for prod
    print(conf)

    deviceHandler = DeviceHandler()

    # Webcam Service
    pipeline = (" ! ").join(
        [
            "v4l2src device=/dev/video0",
            "'image/jpeg,width=640,height=480,framerate=30/1'",
            "v4l2jpegdec",
            "v4l2h264enc",
            "'video/x-h264,level=(string)4'",
        ])
    webcamService = WebcamService__Producer(GstTrack(pipeline), "webcam")
    deviceHandler.add_service(webcamService)

    # Message Service
    messageServiceProducer = MessageService__Producer("messageP")
    deviceHandler.add_service(messageServiceProducer)

    # File Service
    fileServiceConsumer = FileService__Consumer("file")

    async def onFile(file: FileServiceEvent):
        print("Received File of type", file["file_type"])
        print("File content:", file["content"])
        try:
            ser.write(file["content"])
            print("File content sent to Arduino")
            await messageServiceProducer.sendMessage("File was uploaded to Arduino", "info")
        except Exception as e:
            print("Error sending data:", e)

    fileServiceConsumer.on("file", onFile)
    deviceHandler.add_service(fileServiceConsumer)

    url = conf["auth"]["deviceURL"]

    async with APIClient(url) as client:
        client.set_auth_token(conf["auth"]["deviceAuthToken"])
        deviceHandlerTask = asyncio.create_task(
            deviceHandler.connect("{url}/devices/{did}".format(
                url=conf["auth"]["deviceURL"],
                did=conf["auth"]["deviceID"]
            ), client)
        )

        await deviceHandlerTask


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
