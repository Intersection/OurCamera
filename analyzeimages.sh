source $1
source venv/ourcamera-dev/bin/activate
python analyzeimages.py -access_key $AWS_ACCESS_KEY_ID -secret_key $AWS_SECRET_ACCESS_KEY -path_images /tmp/preprocessed -path_labels_map ./data/car_label_map.pbtxt -save_directory /tmp/done

