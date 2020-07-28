import csv
import os
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

key = os.environ['AWS_ACCESS_KEY_ID']
secret = os.environ['AWS_SECRET_ACCESS_KEY']

ERROR_HELP_STRINGS = {
    # Common Errors
    'InternalServerError': 'Internal Server Error, generally safe to retry with exponential back-off',
    'ProvisionedThroughputExceededException':
        'Request rate is too high. If you\'re using a custom retry strategy make \
        sure to retry with exponential back-off.' +
        'Otherwise consider reducing frequency of requests or increasing provisioned capacity for your table or secondary index',
    'ResourceNotFoundException': 'One of the tables was not found, verify table exists before retrying',
    'ServiceUnavailable': 'Had trouble reaching DynamoDB. generally safe to retry with exponential back-off',
    'ThrottlingException': 'Request denied due to throttling, generally safe to retry with exponential back-off',
    'UnrecognizedClientException': 'The request signature is incorrect most likely due to an invalid AWS access key ID or secret key, fix before retrying',
    'ValidationException': 'The input fails to satisfy the constraints specified by DynamoDB, fix input before retrying',
    'RequestLimitExceeded': 'Throughput exceeds the current throughput limit for your account, increase account level throughput before retrying',
}


def create_dynamodb_client(region="us-east-1"):
    return boto3.client("dynamodb", region_name=region, aws_access_key_id=key, aws_secret_access_key=secret)


def create_scan_input(camera_location_id, begin_timestamp, end_timestamp):
    return {
        "TableName": "ourcamera_v2",
        "KeyConditionExpression": "#d7690 = :d7690 And #d7691 BETWEEN :d7691 AND :d7692",
        "ExpressionAttributeNames": {"#d7690": "cameraLocationId", "#d7691": "timestamp"},
        "ExpressionAttributeValues": {":d7690": {"S": str(camera_location_id)}, ":d7691": {"S": str(begin_timestamp)},
                                      ":d7692": {"S": str(end_timestamp)}}
    }


def execute_scan(dynamodb_client, input):
    try:
        response = dynamodb_client.query(**input)
        print("Scan successful.")
        # Handle response
    except ClientError as error:
        handle_error(error)
        raise
    else:
        return response['Items']


def save_response(resp, filename):
    header = ['cameraLocationId', 'timestamp', 'people']

    with open(filename, 'w') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()

        for i in resp:
            writer.writerow({
                'cameraLocationId': i['cameraLocationId']['S'],
                'timestamp': i['timestamp']['S'],
                'people': i['people']['N']
            })


def handle_error(error):
    error_code = error.response['Error']['Code']
    error_message = error.response['Error']['Message']

    error_help_string = ERROR_HELP_STRINGS[error_code]

    print('[{error_code}] {help_string}. Error message: {error_message}'
          .format(error_code=error_code,
                  help_string=error_help_string,
                  error_message=error_message))


def main():
    # Create the DynamoDB Client with the region you want
    dynamodb_client = create_dynamodb_client(region="us-east-1")
    import argparse

    parser = argparse.ArgumentParser(
        description='save camera data stream to csv')
    parser.add_argument(
        'location_id',
        type=int,
        help='camera location ID'
    )
    parser.add_argument(
        'begin_ts',
        type=str,
        help='Beginning timestamp in the format of "%Y-%m-%d %H:%M:%S" like "2020-06-15 11:12:13"'
    )
    parser.add_argument(
        'end_ts',
        type=str,
        help='Enging timestamp in the format of "%Y-%m-%d %H:%M:%S" like "2020-06-15 11:12:13"'
    )
    args = parser.parse_args()
    # print(args)
    # exit()

    loc_id = args.location_id
    begin_ts = int(datetime.strptime(args.begin_ts, '%Y-%m-%d %H:%M:%S').timestamp())
    end_ts = int(datetime.strptime(args.end_ts, '%Y-%m-%d %H:%M:%S').timestamp())

    # Create the dictionary containing arguments for scan call
    scan_input = create_scan_input(camera_location_id=loc_id, begin_timestamp=begin_ts, end_timestamp=end_ts)
    print(scan_input)
    # Call DynamoDB's scan API
    resp = execute_scan(dynamodb_client, scan_input)

    output_fname = f'result_{loc_id}.csv'

    save_response(resp, output_fname)


if __name__ == "__main__":
    main()
