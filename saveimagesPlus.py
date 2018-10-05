r"""Download images from NYC DOT

This executable is used to download DOT images from http://dotsignals.org/:

By inspecting http://dotsignals.org/ you can determine the URL of the camera you are interested in for example
http://207.251.86.238/cctv476.jpg?math=0.29640904121642864

* the url's seem to be static over months.
* DOT does seem to turn the cameras occasionally i.e. move it to cover a different street


Example usage:
    ./download_dot_files \
        --url=http://207.251.86.238/cctv476.jpg?math=0.29640904121642864 \
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

DOT_CAMERA_LIST_URL = "http://dotsignals.org/new-data.php?query="
DOT_CAMERA_ID_URL = "http://dotsignals.org/google_popup.php?cid="
saveDirectory = "/tmp/rawimages/"

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
    now = datetime.datetime.now()
    filePath = saveDirectory + str(cameraId) + "_" + str(now) + ".jpg"
    urlToSave = url + str(cameraId) + append
    urllib.urlretrieve(urlToSave, filePath)
    if (os.path.getsize(filePath) < 11000):
        os.remove(filePath)

class SaveImages:

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
            if i>50:
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Download images every second from dotsignals.org', formatter_class=RawTextHelpFormatter)
    #parser.add_argument('-url', help='the url for the image you want to download')
    parser.add_argument('-save_directory', help='the directory you want to save the images to')
    args = parser.parse_args()
    pool = Pool(processes=20)              # start 4 worker processes
    cameraObjects = SaveImages().fillCameraObjectsWithCameraId(SaveImages().getCameraObjectsWithoutCameraId())
    SaveImages().download_dot_files(pool,cameraObjects)
    while(True):
        SaveImages().download_dot_files(pool,cameraObjects)

