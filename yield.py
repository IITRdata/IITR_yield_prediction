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

Query = """SELECT
	ii.InvoiceNo invoice_num,
    ii.CustomerID cust_id,
    br.ReferrerType referrer_type,
    ROUND(DATEDIFF(CURRENT_DATE, c.Customer_DOB) /365) cust_age,
    c.Gender cust_gender,
    lc.LicenseCategory license_type,
    c.VehicleCategory vehicle_category,
    ((CASE WHEN ii.SettledTotal > ii.InvoiceTotal THEN ii.InvoiceTotal ELSE ii.SettledTotal END) / ii.InvoiceTotal) yield_perc
FROM insuranceinvoice ii
LEFT JOIN customer c USING (CustomerID)
LEFT JOIN branchreferrer br ON c.ReferrerID = br.ReferrerID
LEFT JOIN lookuplicensecategory lc ON lc.LicenseCategoryID = c.License_Category
WHERE ii.SettledDate IS NOT NULL
AND ii.SettledDate >= DATE_ADD(CURRENT_DATE, INTERVAL -12 month)
AND br.ReferrerType IS NOT NULL;
"""

data = connect_and_fecth(endpoint = mysql_creds['aws_endpoint'],
                  user = mysql_creds['db_user'],
                  password = mysql_creds['password'],
                  db_name = mysql_creds['db_name'],
                  port = mysql_creds['port'],
                  query = Query
                )

df = pd.DataFrame(data=data, columns=get_query_column_names(query = Query))

print(df.info())
