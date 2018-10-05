import unittest
from mock import patch
from saveimagesPlus import SaveImages,CameraObject
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
            result = SaveImages().getDOTLocationMapAsJson()
            assert 'markers' in result
            assert isinstance(result["markers"], list)
            assert result["markers"][0]["id"] == "368"

    def test_get_dot_camera_id_for_location_id(self):
        with patch("urllib.urlopen", return_value=self.MockDOTResponseString()) as mock_urlopen:
            result = SaveImages().getDOTCameraIdForLocationId(368)
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

    def test_save_images(self):
        with patch("urllib.urlretrieve") as mock_urlretrieve, \
                patch("os.path.getsize",return_value=5) as mock_getsize, patch("os.remove") as mock_remove:
            SaveImages().saveFile(self.MockCameraObjectsWithoutCameraId.mockObject2,"testpath")
            assert mock_urlretrieve.call_count ==1
            assert mock_getsize.call_count ==1
            assert mock_remove.call_count ==1

        with patch("urllib.urlretrieve") as mock_urlretrieve, \
                patch("os.path.getsize",return_value=50000) as mock_getsize, patch("os.remove") as mock_remove:
            SaveImages().saveFile(self.MockCameraObjectsWithoutCameraId.mockObject2,"testpath")
            assert mock_urlretrieve.call_count ==1
            assert mock_getsize.call_count ==1
            assert mock_remove.call_count ==0




