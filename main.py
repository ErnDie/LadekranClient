#! /usr/bin/env python3

import json
import os
import subprocess
from datetime import datetime

from crosslab.soa_services.file import FileService__Consumer, FileServiceEvent, FileService__Producer
from crosslab.soa_services.webcam import WebcamService__Producer, GstTrack

import asyncio
import serial

from crosslab.api_client import APIClient
from crosslab.soa_client.device_handler import DeviceHandler
from crosslab.soa_services.message import MessageService__Producer, MessageService__Consumer


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
    messageServiceProducer = MessageService__Producer("message")
    deviceHandler.add_service(messageServiceProducer)

    # File Service
    fileServiceConsumer = FileService__Consumer("file")

    async def run_command(command):
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            print(f"Error running command: {command}")
            print(f"Command stderr: {stderr.decode().strip()}")

    async def onFile(file: FileServiceEvent):
        print("Received File of type", file["file_type"])
        print("File content:", file["content"])
        try:
            try:
                os.mkdir(f"{os.getcwd()}/tmp")
            except:
                print("Tmp directory already exists!")

            file_data = file["content"]
            with open(os.path.join(f"{os.getcwd()}/tmp", "tmp.ino"), "wb") as file:
                file.write(file_data)

            start = datetime.now()
            # Run the Arduino CLI commands asynchronously
            await run_command(f"cd {os.getcwd()} && arduino-cli compile --fqbn arduino:avr:uno tmp")
            await run_command(f"arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:uno tmp")
            end = datetime.now()
            print("File uploaded!")
            await messageServiceProducer.sendMessage(f"{end - start}", "info")
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
