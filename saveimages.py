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
import  time

DOT_CAMERA_LIST_URL = "http://dotsignals.org/new-data.php?query="
DOT_CAMERA_ID_URL = "http://dotsignals.org/google_popup.php?cid="
saveDirectory = "/tmp/rawimages/"
outDirectory = "/tmp/preprocessed/"
BUCKET = "personal-ourcamera"
MAX_FILES_TO_DOWNLOAD = 2000
save_to_aws = True

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
        SaveImages().saveFileToS3(filePath,fileName,"raw",outDirectory+"/"+fileName)

class SaveImages:

    class RenameAfterUpload(object):
        def __init__(self, currentFilePath, nextFilePath):
            self._currentFilePath = currentFilePath
            self._nextFilePath = nextFilePath
            self._size = float(os.path.getsize(currentFilePath))
            self._seen_so_far = 0
            self._lock = threading.Lock()

        def __call__(self, bytes_amount):

            with self._lock:
                self._seen_so_far += bytes_amount
                percentage = (self._seen_so_far / self._size) * 100
                print("Percentage" +str(percentage))
                if percentage == 100.0:
                    os.rename(self._currentFilePath, self._nextFilePath)

    class DeleteAfterUpload(object):
        def __init__(self, currentFilePath):
            self._currentFilePath = currentFilePath
            self._size = float(os.path.getsize(currentFilePath))
            self._seen_so_far = 0
            self._lock = threading.Lock()

        def __call__(self, bytes_amount):

            with self._lock:
                self._seen_so_far += bytes_amount
                percentage = (self._seen_so_far / self._size) * 100
                print("Percentage" +str(percentage))
                if percentage == 100.0:
                    os.remove(self._currentFilePath)

    def renameFunction(self,filePath,nextFilePath):
        print()
        os.rename(filePath, nextFilePath)

    def saveFileToS3(self,filePath, fileName,s3BaseDirectory,renamedFilePathOnSuccess):
        if not save_to_aws:
            return
        s3 = boto3.client('s3')
        try:
            if renamedFilePathOnSuccess:
                s3.upload_file(filePath, BUCKET, s3BaseDirectory + "/" +SaveImages().getS3Path(fileName),
                           Callback=self.RenameAfterUpload(filePath,renamedFilePathOnSuccess))
            else:
                s3.upload_file(filePath, BUCKET, s3BaseDirectory + "/" + SaveImages().getS3Path(fileName),
                               Callback=self.DeleteAfterUpload(filePath))

        except Exception as e:
            print("Filepath is "+filePath)
            print("fileName is "+fileName)
            print("s3Directory "+s3BaseDirectory)
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

    def returnTrueToDownloadMoreImages(self,numberFilesDownloadPoint):
        if len([name for name in os.listdir(saveDirectory)])<numberFilesDownloadPoint:
            return True
        return False

    def getTimestampAndLocationId(self,testPath):
        try:
            splits = testPath.split("_")
            if (len(splits) > 0):
                locationId = splits[1]
                timestamp = splits[2][:-4]
                return int(timestamp), int(locationId)
        except:
            return 0, 0
        return 0, 0

    def saveObjectsToFile(self,filePath,objectsToSave):
        with open(filePath, 'w') as outfile:
            json.dump([ob.__dict__ for ob in objectsToSave], outfile)
        self.saveFileToS3(filePath,"cameraobjects","map","")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Download images every second from dotsignals.org', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-save_directory', help='the directory you want to save the images to')
    args = parser.parse_args()
    pool = Pool(processes=20)              # start 4 worker processes
    cameraObjects = SaveImages().fillCameraObjectsWithCameraId(SaveImages().getCameraObjectsWithoutCameraId())
    SaveImages().saveObjectsToFile("/tmp/objects.json",cameraObjects)
    SaveImages().download_dot_files(pool,cameraObjects)
    while (True):
        if SaveImages().returnTrueToDownloadMoreImages(MAX_FILES_TO_DOWNLOAD):
            SaveImages().download_dot_files(pool,cameraObjects)
        else:
            time.sleep(1.0)

