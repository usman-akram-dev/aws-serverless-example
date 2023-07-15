import json
import boto3
from os import environ

import pymysql


client = boto3.client('rds')  # get the rds object


def create_proxy_connection_token(username):
    # get the required parameters to create a token
    hostname = environ.get('DB_LOCATION')  # get the rds proxy endpoint
    port = 3306  # get the database port

    # generate the authentication token -- temporary password
    token = client.generate_db_auth_token(
        DBHostname=hostname,
        Port=port,
        DBUsername=username
    )

    return token


token = create_proxy_connection_token(environ.get('DB_USER'))


def db_ops():
    username = environ.get('DB_USER')

    token = create_proxy_connection_token(username)

    try:
        # create a connection object
        connection = pymysql.connect(
            host=environ.get('DB_LOCATION'),
            # getting the rds proxy endpoint from the environment variables
            user=username,
            password=token,
            db=environ.get('DB_NAME'),
            ssl={"use": True}
        )
        return connection
    except pymysql.MySQLError as e:
        print(e)
        return e


def lambda_handler(event, context):
    conn = db_ops()
    query = "select * from products"
    cursor = conn.cursor()
    cursor.execute(query)
    result = cursor.fetchmany(1)

    return {
        'statusCode': 200,
        'body': json.dumps(result, default=str)
    }
