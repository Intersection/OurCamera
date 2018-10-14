r"""Download images from NYC DOT

This executable is used to download DOT images from http://dotsignals.org/:

This class first pings a DOT backend to get the list of location ids, then associates location ids to camera ids, and
then downloads images.


Example usage:
    ./download_dot_files \
        --save_directory=path/to/data_dir
"""
import json
import urllib
import threading
import datetime
import argparse
from argparse import RawTextHelpFormatter
import os;
from multiprocessing import Pool, TimeoutError
import boto3
from botocore.stub import Stubber
import datetime
import botocore

DOT_CAMERA_LIST_URL = "http://dotsignals.org/new-data.php?query="
DOT_CAMERA_ID_URL = "http://dotsignals.org/google_popup.php?cid="
saveDirectory = "/tmp/rawimages/"
outDirectory = "/tmp/preprocessed/"
BUCKET = "ourcamera"

class CameraObject:
    cameraId = None
    locationId = None
    latitude = None
    longitude = None
    name = None

def saveFile(cameraObject):
    assert isinstance(cameraObject, CameraObject)
    cameraId = cameraObject.cameraId
    url = "http://207.251.86.238/cctv"
    append = ".jpg?math=0.011125243364920934"
    fileName = SaveImages().getStringFormat(cameraObject)
    filePath = saveDirectory+fileName
    urlToSave = url + str(cameraId) + append
    urllib.urlretrieve(urlToSave, filePath)
    if (os.path.getsize(filePath) < 11000):
        os.remove(filePath)
    else:
        SaveImages().saveFileToS3(filePath,fileName)

class SaveImages:

    def saveFileToS3(self,filePath,fileName):
        s3 = boto3.client('s3')
        try:
            s3.upload_file(filePath, BUCKET, SaveImages().getS3Path(fileName))
            os.rename(filePath,outDirectory+fileName)
        except Exception as e:
            print("exception is "+str(e))

    def getS3Path(self,fileName):
        now = datetime.datetime.now()
        return str(now.year)+"/"+str(now.month)+"/"+str(now.day)+"/"+str(now.hour)+"/"+fileName

    def getStringFormat(self,cameraObject):
        epoch = datetime.datetime.now().strftime("%s")
        return str(cameraObject.cameraId) + "_" +str(cameraObject.locationId) + "_" + str(epoch) + ".jpg"

    def download_dot_files(self,pool,cameraObjects):
        print("download_dot_files")
        pool.map(saveFile, cameraObjects)

    def getDOTLocationMapAsJson(self):
        return json.loads(urllib.urlopen(DOT_CAMERA_LIST_URL).read())

    def getDOTCameraIdForLocationId(self,locationId):
        page = urllib.urlopen(DOT_CAMERA_ID_URL+str(locationId)).read()
        cameraId = page.find(".jpg")
        for i in range(0,5):
            if page[cameraId-i]=="v":
                return int(page[cameraId-i+1:cameraId])

    def getCameraObjectsWithoutCameraId(self):
        cameraObjectsWithoutCameraId = []
        i = 0
        for marker in self.getDOTLocationMapAsJson()["markers"]:
            i +=1
            if i>5:
                return cameraObjectsWithoutCameraId
            cameraObject = CameraObject()
            cameraObject.locationId = marker["id"]
            cameraObject.latitude = marker["latitude"]
            cameraObject.longitude = marker["longitude"]
            cameraObject.name = marker["content"]
            cameraObjectsWithoutCameraId.append(cameraObject)
        return cameraObjectsWithoutCameraId


    def fillCameraObjectsWithCameraId(self,cameraObjectsWithoutCameraIds):
        i = 0
        total = len(cameraObjectsWithoutCameraIds)
        for cameraObject in cameraObjectsWithoutCameraIds:
            i +=1
            cameraObject.cameraId =self.getDOTCameraIdForLocationId(cameraObject.locationId)
            print("Filling "+str(i)+" of total "+str(total))
        return cameraObjectsWithoutCameraIds #now filled with cameraIds

    def getJSONStringFromObject(self,cameraObjects):
        return json.dumps(cameraObjects.__dict__)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Download images every second from dotsignals.org', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-save_directory', help='the directory you want to save the images to')
    args = parser.parse_args()
    pool = Pool(processes=20)              # start 4 worker processes
    cameraObjects = SaveImages().fillCameraObjectsWithCameraId(SaveImages().getCameraObjectsWithoutCameraId())
    # saveCameraObjectsToJSONFILEAndUpload
    SaveImages().download_dot_files(pool,cameraObjects)
    #while(True):
    #    SaveImages().download_dot_files(pool,cameraObjects)

