r"""Analyze Traffic Images

This executable is used to annotate traffic images to highlight vehicle types and to produce stats
and graphs for the amount of time bicycle lanes and bus stops are blocked by vehicles:


Example usage:
    ./analyzeimages \
        -path_images /tmp/preprocessed
        -path_labels_map data/car_label_map.pbtxt
        -save_directory /tmp/processed
"""
import random
import sys
import numpy as np
import tensorflow as tf
from saveimages import *

# TODO: Find another way to include object_detection package
sys.path.append('./models-master/research/')

from object_detection.utils import label_map_util, visualization_utils as vis_util

ACCESS_KEY = ""
SECRET_KEY = ""

from PIL import Image

DETECTION_LIMIT = .4


class TrafficResult:
    timestamp = 0
    cameraLocationId = 0
    numberCars = 0
    numberTrucks = 0
    numberPeople = 0


class AnalyzeImages:
    def __init__(self):
        self._table = None

    def createGraph(self):
        pathcpkt = './faster_rcnn_resnet50_coco_2018_01_28/frozen_inference_graph.pb'

        with tf.device('/gpu:1'):
            detection_graph = tf.Graph()
            with detection_graph.as_default():
                od_graph_def = tf.GraphDef()
                with tf.gfile.GFile(pathcpkt, 'rb') as fid:
                    serialized_graph = fid.read()
                    od_graph_def.ParseFromString(serialized_graph)
                    tf.import_graph_def(od_graph_def, name='')
            return detection_graph

    @staticmethod
    def create_category_index(path_labels_map):
        num_classes = 6
        label_map = label_map_util.load_labelmap(path_labels_map)
        categories = label_map_util.convert_label_map_to_categories(label_map, max_num_classes=num_classes,
                                                                    use_display_name=True)
        return label_map_util.create_category_index(categories)

    @staticmethod
    def load_image_into_numpy_array(imageconvert):
        (im_width, im_height) = imageconvert.size
        try:
            return np.array(imageconvert.getdata()).reshape((im_height, im_width, 3)).astype(np.uint8)
        except ValueError:
            return np.array([])

    @staticmethod
    def save_annotated_image(file_name, file_path, s3directory):
        return SaveImages().saveFileToS3(file_path, file_name, s3directory, False, ACCESS_KEY, SECRET_KEY)

    def get_database_instance(self):
        if self._table is not None:
            return self._table

        session = boto3.Session(
            aws_access_key_id=ACCESS_KEY,
            aws_secret_access_key=SECRET_KEY,
            region_name="us-east-1"
        )
        dynamodb = session.resource('dynamodb')
        self._table = dynamodb.Table('ourcamera')
        return self._table

    def logTrafficResult(self, trafficResult):
        if not save_to_aws:
            return
        assert isinstance(trafficResult, TrafficResult)
        self.get_database_instance().put_item(
            Item={
                'timestamp': str(trafficResult.timestamp) + ":" + str(trafficResult.cameraLocationId),
                'cameraLocationId': trafficResult.cameraLocationId,
                'cars': trafficResult.numberCars,
                'trucks': trafficResult.numberTrucks,
                'people': trafficResult.numberTrucks
            }
        )

    def processimages(self, path_images_dir, path_labels_map, save_directory):
        detection_graph = self.createGraph()
        category_index = AnalyzeImages.create_category_index(path_labels_map)

        with detection_graph.as_default():
            with tf.Session(graph=detection_graph) as sess:
                image_tensor = detection_graph.get_tensor_by_name('image_tensor:0')
                detection_boxes = detection_graph.get_tensor_by_name('detection_boxes:0')
                detection_scores = detection_graph.get_tensor_by_name('detection_scores:0')
                detection_classes = detection_graph.get_tensor_by_name('detection_classes:0')
                num_detections = detection_graph.get_tensor_by_name('num_detections:0')

                while (True):
                    for testpath in os.listdir(path_images_dir):
                        start_time = time.time()
                        timestamp, locationId = SaveImages().getTimestampAndLocationId(testpath)
                        if timestamp == 0:
                            os.remove(path_images_dir + "/" + testpath)
                            continue
                        numCars = 0
                        numTrucks = 0
                        num_people = 0

                        try:
                            with Image.open(path_images_dir + '/' + testpath) as image:
                                image_np = AnalyzeImages.load_image_into_numpy_array(image)
                        except IOError:
                            print("Issue opening " + testpath)
                            os.remove(path_images_dir + '/' + testpath)
                            continue

                        if image_np.size == 0:
                            print("Skipping image " + testpath)
                            os.remove(path_images_dir + '/' + testpath)
                            continue

                        # Expand dimensions since the model expects images to have shape: [1, None, None, 3]
                        image_np_expanded = np.expand_dims(image_np, axis=0)
                        # Actual detection.
                        (boxes, scores, classes, num) = sess.run(
                            [detection_boxes, detection_scores, detection_classes, num_detections],
                            feed_dict={image_tensor: image_np_expanded})

                        scores = np.squeeze(scores)
                        boxes = np.squeeze(boxes)
                        for i in range(boxes.shape[0]):
                            if scores[i] > DETECTION_LIMIT:
                                box = tuple(boxes[i].tolist())

                                classes = np.squeeze(classes).astype(np.int32)
                                if classes[i] in category_index.keys():
                                    class_name = category_index[classes[i]]['name']
                                    if class_name == 'car':
                                        numCars = numCars + 1;
                                    elif class_name == 'truck':
                                        numTrucks = numTrucks + 1;
                                    elif class_name == 'pedestrian':
                                        num_people += 1

                        trafficResults = TrafficResult()
                        trafficResults.numberCars = numCars
                        trafficResults.numberTrucks = numTrucks
                        trafficResults.timestamp = timestamp
                        trafficResults.cameraLocationId = locationId
                        trafficResults.numPeople = num_people
                        self.logTrafficResult(trafficResults)

                        print("Process Time " + str(time.time() - start_time))
                        print(f"There are {numCars} cars, {numTrucks} trucks/others and {num_people} people")
                        if (random.randint(0, 100) == 1):
                            # Visualization of the results of a detection.
                            vis_util.visualize_boxes_and_labels_on_image_array(
                                image_np,
                                np.squeeze(boxes),
                                np.squeeze(classes).astype(np.int32),
                                np.squeeze(scores),
                                category_index,
                                min_score_thresh=0.4,
                                use_normalized_coordinates=True,
                                line_thickness=2)
                            print("save_directory " + save_directory)
                            print("testpath " + testpath)
                            Image.fromarray(image_np).save(save_directory + "/" + testpath)
                            AnalyzeImages.save_annotated_image(testpath, save_directory + "/" + testpath, "annotated")
                            os.remove(path_images_dir + '/' + testpath)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Analyze traffic images to determine rate of blocking bike and bus lanes',
        formatter_class=RawTextHelpFormatter
    )

    parser.add_argument('-path_images', help='the folder with all the downloaded images in it')
    parser.add_argument('-path_labels_map', help='the file with the integer to label map')
    parser.add_argument('-save_directory', help='the directory you want to save the annotated images to')
    parser.add_argument('-access_key', help='aws access key')
    parser.add_argument('-secret_key', help='aws secret key')
    args = parser.parse_args()
    ACCESS_KEY = args.access_key
    SECRET_KEY = args.secret_key
    AnalyzeImages().processimages(args.path_images, args.path_labels_map, args.save_directory)
