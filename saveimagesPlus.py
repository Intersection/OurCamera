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

global dictionaryExcludes
dictionaryExcludes= {}
DOT_CAMERA_LIST_URL = "http://dotsignals.org/new-data.php?query="


def saveFile(cameraNumber):
    global dictionaryExcludes
    excludes = []
    if not dictionaryExcludes.has_key(cameraNumber):
        url = "http://207.251.86.238/cctv"
        append = ".jpg?math=0.011125243364920934"
        now = datetime.datetime.now()
        filePath = args.save_directory+str(cameraNumber)+"_"+str(now)+".jpg"
        urlToSave = url + str(cameraNumber)+append
        urllib.urlretrieve(urlToSave, filePath)
        if (os.path.getsize(filePath) < 11000):
            excludes.append(cameraNumber)
            os.remove(filePath)
            print("Exlude "+str(cameraNumber))
        print("Save " + str(cameraNumber))
    return excludes

def download_dot_files(pool):
    global dictionaryExcludes
    total_excludes = []
    excludes = pool.imap_unordered(saveFile,range(500))
    #print("excludes is "+str(excludes))
    if (len(dictionaryExcludes)<2):
        total_excludes = [ent for sublist in excludes for ent in sublist]
        dictionaryExcludes = dict((el, 0) for el in total_excludes)
        print("DictionaryExcludes is "+str(dictionaryExcludes))

    #t = threading.Timer(1.0, download_dot_files).start()

def getDOTLocationMapAsJson():
    return json.loads(urllib.urlretrieve(DOT_CAMERA_LIST_URL).read())

def getDOTCameraIdForLocationId():
    return 1

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Download images every second from dotsignals.org', formatter_class=RawTextHelpFormatter)
    #parser.add_argument('-url', help='the url for the image you want to download')
    parser.add_argument('-save_directory', help='the directory you want to save the images to')
    args = parser.parse_args()
    pool = Pool(processes=20)              # start 4 worker processes

    download_dot_files(pool)
    while(True):
        download_dot_files(pool)

