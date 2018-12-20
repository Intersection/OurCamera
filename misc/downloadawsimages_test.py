import unittest
from mock import patch
from downloadawsimages import *

class TestDownloadAWSImages(unittest.TestCase):

    # Method that gets executed before each test is run in order to set up the test
    def setUp(self):
        pass

    # Method that gets executed before each test is run in order to clean up the execution of the previous test.
    def tearDown(self):
        pass

    @patch('downloadawsimages.boto3')
    def test_download_remote_image_success(self,boto3):
        return_boolean = DownloadAwsImages().download_remote_file("fake", "fake", "fake")
        assert return_boolean

