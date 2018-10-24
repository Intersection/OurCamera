FROM "ubuntu"
RUN apt-get update && yes | apt-get upgrade
RUN mkdir -p /tensorflow/models
RUN apt-get install -y git python-pip
ADD requirements.txt /
RUN pip2 install -r requirements.txt
RUN apt-get install -y protobuf-compiler python-pil python-lxml vim
RUN git clone https://github.com/tensorflow/models.git /tensorflow/models
WORKDIR /tensorflow/models/research
RUN protoc object_detection/protos/*.proto --python_out=.
RUN export PYTHONPATH=$PYTHONPATH:`pwd`:`pwd`/slim
WORKDIR /
ADD http://download.tensorflow.org/models/object_detection/faster_rcnn_resnet50_coco_2018_01_28.tar.gz /
RUN tar xvzf faster_rcnn_resnet50_coco_2018_01_28.tar.gz
ADD car_label_map.pbtxt /
ADD analyzeimages.py /
ADD saveimages.py /
RUN mkdir -p /tmp/rawimages
RUN mkdir -p /tmp/preprocessed
RUN mkdir -p /tmp/done
# ONLY ON AWS RUN source activate tensorflow_p27
COPY startup.sh /
RUN chmod +x ./startup.sh
CMD ["./startup.sh"]


