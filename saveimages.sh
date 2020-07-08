source envvars-dev
source venv/ourcamera-dev/bin/activate
python saveimages.py --access_key $AWS_ACCESS_KEY_ID --secret_key $AWS_SECRET_ACCESS_KEY
