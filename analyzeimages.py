r"""Analyze Traffic Images

This executable is used to annotate traffic images to highlight vehicle types and to produce stats
and graphs for the amount of time bicycle lanes and bus stops are blocked by vehicles:


Example usage:
    ./analyzeimages \
        -path_images ./data/rawimages/
        -path_labels_map data/car_label_map.pbtxt
        -save_directory data/processedimages/
"""

import sys

#from matplotlib.ticker import FormatStrFormatter, FuncFormatter

sys.path.append('./models-master/research/')
from object_detection.utils import label_map_util
from object_detection.utils import visualization_utils as vis_util

import argparse
from argparse import RawTextHelpFormatter
import time
import numpy as np
import os
import tensorflow as tf
import csv
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
from io import StringIO
# from matplotlib import pyplot as plt
import matplotlib.path as mpltPath

from PIL import Image
import scipy.misc


def processimages(path_images_dir, path_labels_map,save_directory):
    pathcpkt = 'data/output_inference_graph.pb/frozen_inference_graph_resnet_50.pb'
    csv_file = 'data/csvfile.csv'
    num_classes = 6

    detection_graph = tf.Graph()

    with detection_graph.as_default():
        od_graph_def = tf.GraphDef()
        with tf.gfile.GFile(pathcpkt, 'rb') as fid:
            serialized_graph = fid.read()
            od_graph_def.ParseFromString(serialized_graph)
            tf.import_graph_def(od_graph_def, name='')

    label_map = label_map_util.load_labelmap(path_labels_map)
    categories = label_map_util.convert_label_map_to_categories(label_map, max_num_classes=num_classes,
                                                                use_display_name=True)
    category_index = label_map_util.create_category_index(categories)

    f = open(csv_file, 'w')


    def load_image_into_numpy_array(imageconvert):
        (im_width, im_height) = imageconvert.size
        try:
            return np.array(imageconvert.getdata()).reshape(
                (im_height, im_width, 3)).astype(np.uint8)
        except ValueError:
            return np.array([])

    with detection_graph.as_default():
        with tf.Session(graph=detection_graph) as sess:
            # Definite input and output Tensors for detection_graph
            image_tensor = detection_graph.get_tensor_by_name('image_tensor:0')
            # Each box represents a part of the image where a particular object was detected.
            detection_boxes = detection_graph.get_tensor_by_name('detection_boxes:0')
            # Each score represent how level of confidence for each of the objects.
            # Score is shown on the result image, together with the class label.
            detection_scores = detection_graph.get_tensor_by_name('detection_scores:0')
            detection_classes = detection_graph.get_tensor_by_name('detection_classes:0')
            num_detections = detection_graph.get_tensor_by_name('num_detections:0')

            while(True):
                for testpath in os.listdir(path_images_dir):

                    start_time = time.time()
                    timestamp = testpath.split(".jpg")[0]
                    numCars =0
                    numTrucks = 0

                    try:
                        image = Image.open(path_images_dir + '/' + testpath)
                        image_np = load_image_into_numpy_array(image)
                    except IOError:
                        print("Issue opening "+testpath)
                        continue

                    if image_np.size == 0:
                        print("Skipping image "+testpath)
                        continue
                    # Expand dimensions since the model expects images to have shape: [1, None, None, 3]
                    image_np_expanded = np.expand_dims(image_np, axis=0)
                    # Actual detection.
                    (boxes, scores, classes, num) = sess.run(
                        [detection_boxes, detection_scores, detection_classes, num_detections],
                        feed_dict={image_tensor: image_np_expanded})

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
                    scores = np.squeeze(scores)
                    boxes = np.squeeze(boxes)
                    for i in range(boxes.shape[0]):
                        if scores[i] > .4:
                            box = tuple(boxes[i].tolist())


                            classes = np.squeeze(classes).astype(np.int32)
                            if classes[i] in category_index.keys():
                                class_name = category_index[classes[i]]['name']
                            else:
                                class_name = 'N/A'

                            if class_name == 'car':
                                numCars=numCars+1;


                            elif class_name == 'truck' or class_name == 'police' or class_name == 'ups':
                                numTrucks=numTrucks+1;


                    # write to a csv file whenever there is a vehicle, how many and of what type with timestamp

                    print("Process Time " + str(time.time() - start_time))
                    print("There are "+str(numCars)+" cars and "+str(numTrucks)+" trucks/others");
                    scipy.misc.imsave(save_directory + testpath, image_np)
                    os.remove(path_images_dir + '/' + testpath)
        f.close()
        return csv_file





if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Analyze traffic images to determine rate of blocking bike'
                    'and bus lanes', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-path_images', help='the folder with all the downloaded images in it')
    parser.add_argument('-path_labels_map', help='the file with the integer to label map')
    parser.add_argument('-save_directory', help='the directory you want to save the annotated images to')
    args = parser.parse_args()
    processimages(args.path_images,args.path_labels_map,args.save_directory)
