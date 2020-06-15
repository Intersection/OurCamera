r"""Download images from NYC DOT

This executable is used to download DOT images from http://nyctmc.org/:

This class first pings a DOT backend to get the list of location ids, then associates location ids to camera ids, and
then downloads images.


Example usage:
    python saveimages.py
"""
import datetime
import errno
import json
import logging
import os
import threading
import time
import argparse
from multiprocessing import Pool

import boto3
import requests
import urllib3

DOT_CAMERA_LIST_URL = "https://webcams.nyctmc.org/new-data.php?query="
# DOT_CAMERA_LIST_URL = "https://dotsignals.org/new-data.php?query="
DOT_CAMERA_ID_URL = "https://webcams.nyctmc.org/google_popup.php?cid="
# DOT_CAMERA_ID_URL = "https://dotsignals.org/google_popup.php?cid="
saveDirectory = "/tmp/rawimages/"
outDirectory = "/tmp/preprocessed/"
BUCKET = "intersection-ourcamera"
MAX_FILES_TO_DOWNLOAD = 2000
NUMBER_FILES_DOWNLOAD_LIMIT = 1000
save_to_aws = True
ACCESS_KEY = ""
SECRET_KEY = ""

logging.basicConfig(
    format='{asctime} {levelname}: {message} {pathname}:{lineno}',
    style='{',
    level=os.getenv('LOGLEVEL', 'INFO')
)

log = logging.getLogger(__name__)
log.setLevel('DEBUG')

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Temporary fix to alleviate SSL not updated on the server side
VERIFY_SSL_CERT = False
VALID_IMG_CONTENT_SIZE = 11000


class CameraObject:

    def __init__(self) -> None:
        super().__init__()

        self.cameraId = None
        self.locationId = None
        self.latitude = None
        self.longitude = None
        self.name = None

    def __repr__(self):
        return f"{self.name} [{self.cameraId}:{self.locationId}] (lat={self.latitude}, lon={self.longitude})"


def save_file(camera_object):
    assert isinstance(camera_object, CameraObject)
    camera_id = camera_object.cameraId
    url = "http://207.251.86.238/cctv"
    append = ".jpg?math=0.011125243364920934"
    file_name = SaveImages.get_string_format(camera_object)
    file_path = saveDirectory + file_name
    url_to_save = url + str(camera_id) + append
    log.info("trying to download" + url_to_save)

    try:
        img_content = requests.get(url_to_save)
        img_content.raise_for_status()
    except requests.exceptions.HTTPError:
        log.exception(f"Could not make GET request to image with url={url_to_save}")
        raise
    else:
        if len(img_content.content) > VALID_IMG_CONTENT_SIZE:
            try:
                with open(file_path, 'wb') as f:
                    f.write(img_content.content)
                    log.info(f'Wrote {len(img_content.content)} bytes to {file_path}')
            except IOError:
                logging.exception(f"Could not write image content to file={file_path}")
                raise
            else:
                SaveImages().save_file_to_s3(file_path, file_name, "raw", outDirectory + "/" + file_name, ACCESS_KEY,
                                             SECRET_KEY)


class RenameAfterUpload(object):
    def __init__(self, current_file_path, next_file_path):
        self._current_file_path = current_file_path
        self._next_file_path = next_file_path
        self._size = float(os.path.getsize(current_file_path))
        self._seen_so_far = 0
        self._lock = threading.Lock()

    def __call__(self, bytes_amount):
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            if percentage == 100.0:
                os.rename(self._current_file_path, self._next_file_path)


class DeleteAfterUpload(object):
    def __init__(self, current_file_path):
        self._current_file_path = current_file_path
        self._size = float(os.path.getsize(current_file_path))
        self._seen_so_far = 0
        self._lock = threading.Lock()

    def __call__(self, bytes_amount):
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            if percentage == 100.0:
                os.remove(self._current_file_path)


class SaveImages:
    def save_file_to_s3(self, file_path, file_name, s3_base_directory, renamed_file_path_on_success, key, secret):
        if not save_to_aws:
            return
        s3 = boto3.client('s3',
                          aws_access_key_id=key,
                          aws_secret_access_key=secret
                          )

        s3path = s3_base_directory + "/" + SaveImages.get_s3_path(file_name)
        try:
            if renamed_file_path_on_success:
                s3.upload_file(file_path, BUCKET, s3path,
                               Callback=RenameAfterUpload(file_path, renamed_file_path_on_success))
            else:
                s3.upload_file(file_path, BUCKET, s3path,
                               Callback=DeleteAfterUpload(file_path))
        except Exception as e:
            log.exception(f"Could not upload {file_path} to s3://{BUCKET}/{s3path}")
        else:
            log.info(f"Wrote {file_name} to s3://{BUCKET}/{s3path}; renamed={renamed_file_path_on_success}")

    @staticmethod
    def get_s3_path(file_name):
        now = datetime.datetime.now()
        return str(now.year) + "/" + str(now.month) + "/" + str(now.day) + "/" + str(now.hour) + "/" + file_name

    @staticmethod
    def get_string_format(camera_object):
        epoch = datetime.datetime.now().strftime("%s")
        return str(camera_object.cameraId) + "_" + str(camera_object.locationId) + "_" + str(epoch) + ".jpg"

    @staticmethod
    def download_dot_files(task_pool, camera_objects):
        log.info("download_dot_files")
        try:
            task_pool.map(save_file, camera_objects)
        except:
            log.info("failed creating map")
            task_pool.join()
            task_pool.close()

    @staticmethod
    def getDOTLocationMapAsJson():
        try:
            resp = requests.get(DOT_CAMERA_LIST_URL, verify=VERIFY_SSL_CERT)
        except:
            log.exception(f"Coudln't make GET request to url={DOT_CAMERA_LIST_URL}")
            log.info("FAILED First version")
            raise
        else:
            if resp.status_code != 200:
                log.exception(f"Response code for url={DOT_CAMERA_LIST_URL} is={resp.status_code} - not OK")
                raise requests.RequestException(f"Bad status code for GET request to url={DOT_CAMERA_LIST_URL}")

            return resp.json()

    @staticmethod
    def getDOTCameraIdForLocationId(locationId):
        page = requests.get(DOT_CAMERA_ID_URL + str(locationId), verify=VERIFY_SSL_CERT).text
        cameraId = page.find(".jpg")
        log.info(f'CameraId={cameraId}')
        for i in range(0, 5):
            if page[cameraId - i] == "v":
                return int(page[cameraId - i + 1:cameraId])

    @staticmethod
    def getCameraObjectsWithoutCameraId():
        cameraObjectsWithoutCameraId = []
        i = 0
        loc_markers = SaveImages.getDOTLocationMapAsJson()["markers"]
        log.info(f"Got {len(loc_markers)} camera locations withought ID to fill")
        for marker in loc_markers:
            i += 1
            if i > NUMBER_FILES_DOWNLOAD_LIMIT:
                log.info(f"Got more than {NUMBER_FILES_DOWNLOAD_LIMIT} cameras to work with. Exiting.")
                return cameraObjectsWithoutCameraId
            cameraObject = CameraObject()
            cameraObject.locationId = marker["id"]
            cameraObject.latitude = marker["latitude"]
            cameraObject.longitude = marker["longitude"]
            cameraObject.name = marker["content"]
            cameraObjectsWithoutCameraId.append(cameraObject)
        return cameraObjectsWithoutCameraId

    @staticmethod
    def fillCameraObjectsWithCameraId(cameraObjectsWithoutCameraIds):
        i = 0
        total = len(cameraObjectsWithoutCameraIds)
        for cameraObject in cameraObjectsWithoutCameraIds:
            i += 1
            cameraObject.cameraId = SaveImages.getDOTCameraIdForLocationId(cameraObject.locationId)
            log.warn("Filling " + str(i) + " of total " + str(total))
        return cameraObjectsWithoutCameraIds  # now filled with cameraIds

    @staticmethod
    def getJSONStringFromObject(cameraObjects):
        return json.dumps(cameraObjects.__dict__)

    @staticmethod
    def returnTrueToDownloadMoreImages(numberFilesDownloadPoint):
        if len([name for name in os.listdir(outDirectory)]) < numberFilesDownloadPoint:
            return True
        return False

    @staticmethod
    def getTimestampAndLocationId(testPath):
        try:
            splits = testPath.split("_")
            if (len(splits) > 0):
                locationId = splits[1]
                timestamp = splits[2][:-4]
                return int(timestamp), int(locationId)
        except:
            return 0, 0
        return 0, 0

    def saveObjectsToFile(self, filePath, objectsToSave):
        with open(filePath, 'w') as outfile:
            json.dump([ob.__dict__ for ob in objectsToSave], outfile)
        self.save_file_to_s3(filePath, "cameraobjects", "map", "", ACCESS_KEY, SECRET_KEY)

    @staticmethod
    def makeSureDirectoriesExist():
        SaveImages.mkdir_p(saveDirectory)
        SaveImages.mkdir_p(outDirectory)

    @staticmethod
    def mkdir_p(path):
        try:
            os.makedirs(path)
        except OSError as exc:  # Python >2.5
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Save images', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--access_key', help='aws access key')
    parser.add_argument('--secret_key', help='aws secret key')
    args = parser.parse_args()
    ACCESS_KEY = args.access_key
    SECRET_KEY = args.secret_key
    SaveImages.makeSureDirectoriesExist()

    # TODO: Substitute multiprocessing with async / greenlets programming
    pool = Pool(processes=20)  # start 4 worker processes
    cameraObjects = SaveImages.fillCameraObjectsWithCameraId(SaveImages.getCameraObjectsWithoutCameraId())
    # log.info("cameraObjects " + str(cameraObjects))
    SaveImages().saveObjectsToFile("/tmp/objects.json", cameraObjects)
    SaveImages.download_dot_files(pool, cameraObjects)
    while (True):
        try:
            if SaveImages.returnTrueToDownloadMoreImages(MAX_FILES_TO_DOWNLOAD):
                SaveImages.download_dot_files(pool, cameraObjects)
            else:
                log.info("sleeping")
                time.sleep(10.0)
        except:
            pool.close()
            pool.join()
            break
