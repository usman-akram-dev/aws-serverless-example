# https://github.com/aws/aws-cdk/issues/10820

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
    # token = create_proxy_connection_token(username)

    try:
        # create a connection object

        connection = pymysql.connect(
            host=environ.get('DB_LOCATION'),
            # getting the rds proxy endpoint from the environment variables
            user=environ.get('DB_USER'),
            password=token,
            db=environ.get('DB_NAME'),
            ssl={"use": True},
            client_flag=pymysql.constants.CLIENT.MULTI_STATEMENTS            
        )
        return connection
    except pymysql.MySQLError as e:
        print(e)
        return e



def lambda_handler(event, context):
    conn = db_ops()
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS products (name VARCHAR(100), description VARCHAR(100), price INTEGER); insert into products (name, description, price) values ('PR001', 'Product 1', 100);")
    # query = "create table products (name VARCHAR, description VARCHAR, price INTEGER)"
    # cursor.execute(query)
    conn.commit()
    conn.close()
    return {
        'statusCode': 200
    }
