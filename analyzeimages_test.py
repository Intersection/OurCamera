import unittest
from mock import patch
import copy
import tensorflow as tf
from analyzeimages import *


class TestAnalyzeImages(unittest.TestCase):
    # Method that gets executed before each test is run in order to set up the test
    def setUp(self):
        pass

    # Method that gets executed before each test is run in order to clean up the execution of the previous test.
    def tearDown(self):
        pass

    def test_setup_tensorflow(self):
        graph = AnalyzeImages().createGraph()
        assert graph.__class__.__name__ == "Graph"
        assert graph != None

    def test_create_category_index(self):
        category_index = AnalyzeImages.create_category_index("./test.pbtxt")
        assert category_index.__class__.__name__ == "dict"
        assert 1 in category_index
        assert "name" in category_index[1]
        assert category_index[1]["name"] == "test"






