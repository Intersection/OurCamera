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

from attr import dataclass


DOT_CAMERA_LIST_URL = "https://webcams.nyctmc.org/new-data.php?query="
# DOT_CAMERA_LIST_URL = "https://dotsignals.org/new-data.php?query="
DOT_CAMERA_ID_URL = "https://webcams.nyctmc.org/google_popup.php?cid="
# DOT_CAMERA_ID_URL = "https://dotsignals.org/google_popup.php?cid="
saveDirectory = "/tmp/rawimages"
outDirectory = "/tmp/preprocessed"
BUCKET = "intersection-ourcamera"

save_to_aws = True
ACCESS_KEY = ""
SECRET_KEY = ""


@dataclass(frozen=True)
class SaveImagesConfig:
    MAX_FILES_TO_DOWNLOAD = 2000
    NUMBER_FILES_DOWNLOAD_LIMIT = 1000


# noinspection PyArgumentList
logging.basicConfig(
    style='{',
    format='{asctime} {levelname}: {message} {pathname}:{lineno}'
)

log = logging.getLogger(__name__)

log_level = str(os.getenv('LOG_LEVEL', 'INFO'))
log.setLevel(log_level)

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
    file_path = os.path.join(saveDirectory, file_name)
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
                rename_on_success = os.path.join(outDirectory, file_name)
                SaveImages.save_file_to_s3(file_path, file_name, "raw", rename_on_success, ACCESS_KEY, SECRET_KEY)


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
                log.info(f'File @{self._current_file_path} {"exists" if os.path.exists(self._current_file_path) else "does not exist"}')
                os.rename(self._current_file_path, self._next_file_path)

    def __str__(self):
        return f'{self.__class__.__name__}({self._current_file_path}, {self._next_file_path})'


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

    def __str__(self):
        return f'{self.__class__.__name__}({self._current_file_path})'


class SaveImages:
    @staticmethod
    def save_file_to_s3(fpath, file_name, s3_base_directory, rename_on_success, key, secret):
        if not save_to_aws:
            return

        s3 = boto3.client('s3', aws_access_key_id=key, aws_secret_access_key=secret)
        s3path = '/'.join([s3_base_directory, SaveImages.get_s3_path(file_name)])

        callback = RenameAfterUpload(fpath, rename_on_success) if rename_on_success != "" else DeleteAfterUpload(fpath)
        s3.upload_file(fpath, BUCKET, s3path, Callback=callback)
        log.info(f"Wrote {file_name} to s3://{BUCKET}/{s3path}; callback={callback}")

    @staticmethod
    def get_s3_path(file_name):
        now = datetime.datetime.now()
        return '/'.join([str(v) for v in [now.year, now.month, now.day, now.hour, file_name]])

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
            log.exception("Failed running save_file() worker processes")
            raise

    @staticmethod
    def get_dot_location_map_as_json():
        try:
            resp = requests.get(DOT_CAMERA_LIST_URL, verify=VERIFY_SSL_CERT)
        except:
            log.exception(f"Could not make GET request to url={DOT_CAMERA_LIST_URL}")
            log.info("FAILED First version")
            raise
        else:
            if resp.status_code != 200:
                log.exception(f"Response code for url={DOT_CAMERA_LIST_URL} is={resp.status_code} - not OK")
                raise requests.RequestException(f"Bad status code for GET request to url={DOT_CAMERA_LIST_URL}")

            return resp.json()

    @staticmethod
    def get_dot_camera_id_for_location_id(location_id):
        page = requests.get(DOT_CAMERA_ID_URL + str(location_id), verify=VERIFY_SSL_CERT).text
        camera_id = page.find(".jpg")
        log.info(f'CameraId={camera_id}')
        for i in range(0, 5):
            if page[camera_id - i] == "v":
                return int(page[camera_id - i + 1:camera_id])

    @staticmethod
    def get_camera_objects_without_camera_id():
        camera_objects_without_camera_id = []
        i = 0
        loc_markers = SaveImages.get_dot_location_map_as_json()["markers"]
        log.info(f"Got {len(loc_markers)} camera locations without ID to fill")
        for marker in loc_markers:
            i += 1
            if i > SaveImagesConfig.NUMBER_FILES_DOWNLOAD_LIMIT:
                log.info(f"Got more than {SaveImagesConfig.NUMBER_FILES_DOWNLOAD_LIMIT} cameras to work with. Exiting.")
                return camera_objects_without_camera_id
            camera_object = CameraObject()
            camera_object.locationId = marker["id"]
            camera_object.latitude = marker["latitude"]
            camera_object.longitude = marker["longitude"]
            camera_object.name = marker["content"]
            camera_objects_without_camera_id.append(camera_object)
        return camera_objects_without_camera_id

    @staticmethod
    def fill_camera_objects_with_camera_id(camera_objects):
        i = 0
        total = len(camera_objects)
        for cam_obj in camera_objects:
            i += 1
            cam_obj.cameraId = SaveImages.get_dot_camera_id_for_location_id(cam_obj.locationId)
            log.warning("Filling " + str(i) + " of total " + str(total))
        return camera_objects  # now filled with cameraIds

    @staticmethod
    def get_json_string_from_object(camera_objects):
        return json.dumps(camera_objects.__dict__)

    @staticmethod
    def return_true_to_download_more_images(number_files_download_point):
        if len(os.listdir(outDirectory)) < number_files_download_point:
            return True
        return False

    @staticmethod
    def get_timestamp_and_location_id(test_path):
        try:
            splits = test_path.split("_")
            if len(splits) > 0:
                location_id = splits[1]
                timestamp = splits[2][:-4]
                return int(timestamp), int(location_id)
        except:
            pass
        return 0, 0

    @staticmethod
    def save_objects_to_file(file_path, objects_to_save):
        with open(file_path, 'w') as outfile:
            json.dump([ob.__dict__ for ob in objects_to_save], outfile)
        SaveImages.save_file_to_s3(file_path, "cameraobjects", "map", "", ACCESS_KEY, SECRET_KEY)

    @staticmethod
    def make_sure_directories_exist():
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
    parser = argparse.ArgumentParser(description='Save images')
    parser.add_argument('--access_key', help='aws access key')
    parser.add_argument('--secret_key', help='aws secret key')
    args = parser.parse_args()

    ACCESS_KEY = os.environ['AWS_ACCESS_KEY_ID']
    SECRET_KEY = os.environ['AWS_SECRET_ACCESS_KEY']
    
    SaveImages.make_sure_directories_exist()

    # TODO: Substitute multiprocessing with async / greenlets programming
    pool = Pool(processes=20)  # start 4 worker processes
    cameraObjects = SaveImages.fill_camera_objects_with_camera_id(SaveImages.get_camera_objects_without_camera_id())
    # log.info("cameraObjects " + str(cameraObjects))
    SaveImages.save_objects_to_file("/tmp/objects.json", cameraObjects)
    SaveImages.download_dot_files(pool, cameraObjects)
    try:
        while True:
            if SaveImages.return_true_to_download_more_images(SaveImagesConfig.MAX_FILES_TO_DOWNLOAD):
                SaveImages.download_dot_files(pool, cameraObjects)
            else:
                log.info("sleeping")
                time.sleep(10.0)
    except:
        log.exception("An error occurred while downloading files. Exiting.")
    finally:
        pool.close()
        pool.join()
