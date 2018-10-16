FROM "ubuntu"
RUN apt-get update && yes | apt-get upgrade
RUN mkdir -p /tensorflow/models
RUN apt-get install -y git python-pip
ADD requirements.txt /
RUN pip2 install -r requirements.txt
RUN apt-get install -y protobuf-compiler python-pil python-lxml
RUN git clone https://github.com/tensorflow/models.git /tensorflow/models
WORKDIR /tensorflow/models/research
RUN protoc object_detection/protos/*.proto --python_out=.
RUN export PYTHONPATH=$PYTHONPATH:`pwd`:`pwd`/slim
ADD analyzeimages.py /
ADD saveimages.py.py /
RUN mkdir -p /tmp/rawimages
RUN mkdir -p /tmp/preprocessed
RUN mkdir -p /tmp/done
# ONLY ON AWS RUN source activate tensorflow_p27
CMD [ "python2", "./analyzeimages.py" ]


