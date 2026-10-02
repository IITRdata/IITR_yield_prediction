import pandas as pd
import numpy as np
import mysql.connector
from mysql.connector import Error
from credentials import mysql_creds
from sql_metadata import Parser

# function definitions.

def connect_and_fecth (endpoint: str,
                       user: str,
                       password: str,
                       db_name: str,
                       port: int,
                       query: str):

    try:
        connection = mysql.connector.connect(
            host=endpoint,
            user=user,
            password=password,
            database=db_name,
            port=port
        )

        if connection.is_connected():
            print("Successfully connected to MySQL server.")

            cursor = connection.cursor()
            cursor.execute(query)
            results = cursor.fetchall()

    except Error as e:
        print(f"{e}")

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


    return results

def get_query_column_names(query: str):
    parser = Parser(query)

    return parser.output_columns

##################### Query for Data Extraction ############################

Query = """SELECT CustomerID,  Customer_DOB FROM customer LIMIT 1;"""

data = connect_and_fecth(endpoint = mysql_creds['aws_endpoint'],
                  user = mysql_creds['db_user'],
                  password = mysql_creds['password'],
                  db_name = mysql_creds['db_name'],
                  port = mysql_creds['port'],
                  query = Query
                )

df = pd.DataFrame(data=data, columns=get_query_column_names(query = Query))

print(df.head())
