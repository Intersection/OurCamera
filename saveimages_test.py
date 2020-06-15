import unittest
from mock import patch
from saveimages import *
import copy

class TestSaveImages(unittest.TestCase):

    # Method that gets executed before each test is run in order to set up the test
    def setUp(self):
        pass

    # Method that gets executed before each test is run in order to clean up the execution of the previous test.
    def tearDown(self):
        pass


    class MockOSPath:
        def getsize(self,path):
            return 5

    class MockCameraObjectsWithoutCameraId:
        mockObject = CameraObject()
        mockObject.latitude = 123.123
        mockObject.longitude = 123.123
        mockObject.locationId = 123
        mockObjects =  [mockObject]
        mockObject2 = copy.deepcopy(mockObject)
        mockObject2.cameraId = 126
        mockObjects2 = [mockObject2]
        mockJsonString2 = '{"latitude": 123.123, "locationId": 123, "cameraId": 126, "longitude": 123.123}'


    class MockDOTLocationMapAsJson:
        mocks = {"markers": [{
                "id": "368",
                "latitude": "40.79142677512476",
                "longitude": "-73.93807411193848",
                "title": "images\/camera1.png",
                "icon": "images\/camera1.png",
                "content": "1 Ave @ 110 St"
            },{
                "id": "369",
                "latitude": "40.123",
                "longitude": "-73.123",
                "title": "images\/camera1.png",
                "icon": "images\/camera1.png",
                "content": "1 Ave @ 110 St"
            }]}

    class MockDOTResponseJson:
        def read(self):
            return """
            {"markers": [{
                "id": "368",
                "latitude": "40.79142677512476",
                "longitude": "-73.93807411193848",
                "title": "images\/camera1.png",
                "icon": "images\/camera1.png",
                "content": "1 Ave @ 110 St"
            }]}
                    """

    class MockDOTResponseString:
        def read(self):
            return """
            var currentImage = imageID;document.getElementById(currentImage).src = '
            http://207.251.86.238/cctv261.jpg'+'?math=';
                    """


    def test_get_dot_location_map_as_json(self):
        with patch("urllib.urlretrieve", return_value=self.MockDOTResponseJson()) as mock_urlopen:
            result = SaveImages.getDOTLocationMapAsJson()
            assert 'markers' in result
            assert isinstance(result["markers"], list)
            assert result["markers"][0]["id"] == "368"

    def test_get_dot_camera_id_for_location_id(self):
        with patch("urllib.urlopen", return_value=self.MockDOTResponseString()) as mock_urlopen:
            result = SaveImages.getDOTCameraIdForLocationId(368)
            print("Result is " + str(result))
            assert result == 261

    def test_get_array_of_camera_objects_without_camera_id(self):
        with patch.object(SaveImages, 'getDOTLocationMapAsJson', return_value=self.MockDOTLocationMapAsJson.mocks) as mock_method:
            cameraObjects = SaveImages().getCameraObjectsWithoutCameraId()
            assert isinstance(cameraObjects[0],CameraObject)
            assert cameraObjects[0].cameraId == None
            assert cameraObjects[0].longitude == "-73.93807411193848"
            assert cameraObjects[0].latitude == "40.79142677512476"
            assert isinstance(cameraObjects[1], CameraObject)
            assert cameraObjects[1].cameraId == None
            assert cameraObjects[1].longitude == "-73.123"
            assert cameraObjects[1].latitude == "40.123"

    def test_add_camera_ids_to_camera_objects(self):
        with patch.object(SaveImages,'getDOTCameraIdForLocationId',return_value= 261) as mock_id:
            mockObjects = self.MockCameraObjectsWithoutCameraId.mockObjects
            assert isinstance(mockObjects[0], CameraObject)
            assert mockObjects[0].cameraId == None
            SaveImages().fillCameraObjectsWithCameraId(mockObjects)
            assert mockObjects[0].cameraId == 261

    @patch('saveimages.boto3')
    def test_save_images(self,boto3):
        with patch("urllib.urlretrieve") as mock_urlretrieve, \
                patch("os.path.getsize",return_value=5) as mock_getsize, patch("os.remove") as mock_remove:
            saveFile(self.MockCameraObjectsWithoutCameraId.mockObject2)
            assert mock_urlretrieve.call_count ==1
            assert mock_getsize.call_count ==1
            assert mock_remove.call_count ==1

        with patch("urllib.urlretrieve") as mock_urlretrieve2, \
                patch("os.path.getsize",return_value=50000) as mock_getsize2, patch("os.remove") as mock_remove2,\
                patch("os.rename") as mock_rename2:
            saveFile(self.MockCameraObjectsWithoutCameraId.mockObject2)
            assert mock_urlretrieve2.call_count ==1
            assert mock_getsize2.call_count ==1
            assert mock_remove2.call_count ==0

    def test_get_JSON_String_Object_from_Class(self):
        assert self.MockCameraObjectsWithoutCameraId.mockJsonString2 == SaveImages().getJSONStringFromObject(self.MockCameraObjectsWithoutCameraId.mockObject2)

    def test_return_true_when_able_to_download(self):
        with patch("os.listdir", return_value=["test1","test2"]) as mock_getsize:
            assert SaveImages().returnTrueToDownloadMoreImages(4)
            assert SaveImages().returnTrueToDownloadMoreImages(1) == False

    def test_get_timestamp_and_location_id(self):
        timestamp,locationId = SaveImages().getTimestampAndLocationId("ignore_1_1539560991.jpg")
        assert timestamp == 1539560991
        assert locationId == 1

        timestamp,locationId = SaveImages().getTimestampAndLocationId(".DS_Store")
        assert timestamp == 0
        assert locationId == 0

