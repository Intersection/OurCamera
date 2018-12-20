
import boto3
import botocore
import argparse
from argparse import RawTextHelpFormatter


ACCESS_KEY = ""
SECRET_KEY = ""

class DownloadAwsImages:

    def download_remote_file(self , bucket_name, file_key, local_path):
        s3 = boto3.resource('s3',
            aws_access_key_id = ACCESS_KEY,
            aws_secret_access_key = SECRET_KEY)
        try:
            s3.Bucket(bucket_name).download_file(file_key, local_path)
            return True
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                print("The object does not exist.")
            else:
                raise
        return False

    def get_list_of_aws_objects(self, bucket_path):
        prefix = "raw/"
        s3 = boto3.client("s3")
        paginator = s3.get_paginator("list_objects")
        page_iterator = paginator.paginate(Bucket=bucket_path, Prefix=prefix)
        len_prefix = len(prefix)
        bucket_object_list = []
        for page in page_iterator:
            if "Contents" in page:
                for key in page["Contents"]:
                    keyString = key["Key"]
                    key_split_folder = keyString.split("/")
                    file_path = key_split_folder[len(key_split_folder)-1]
                    key_split_path = file_path.split("_")
                    if (key_split_path[1] == "932"):
                        bucket_object_list.append(keyString)
                        self.download_remote_file("intersection-ourcamera",keyString,"/Users/abell/Downloads/932/"+file_path)
                    elif (key_split_path[1] == "1161"):
                        bucket_object_list.append(keyString)
                        self.download_remote_file("intersection-ourcamera",keyString,"/Users/abell/Downloads/1161/"+file_path)
                    elif (key_split_path[1] == "529"):
                        bucket_object_list.append(keyString)
                        self.download_remote_file("intersection-ourcamera",keyString,"/Users/abell/Downloads/529/"+file_path)
                    elif (key_split_path[1] == "1116"):
                        bucket_object_list.append(keyString)
                        self.download_remote_file("intersection-ourcamera",keyString,"/Users/abell/Downloads/1116/"+file_path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Save images', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-access_key', help='aws access key')
    parser.add_argument('-secret_key', help='aws secret key')
    args = parser.parse_args()
    ACCESS_KEY = args.access_key
    SECRET_KEY = args.secret_key
    DownloadAwsImages().get_list_of_aws_objects("intersection-ourcamera")