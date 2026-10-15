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
    apm.region_mapping region,
    apm.resource_score economic_score,
    apm.education_and_occupation_score professional_score,
    IF(opd.OPD_InsuranceIndicator = 'Y',1,0) opd_has_insurance,
    IF(opd.OPD_InsuranceClaimNo IS NOT NULL,1,0) opd_provided_claim_num,
    IF(dp.num_photos >= 1, 1,0) has_damage_photos,
    IF(br.ReferrerID=180,'ACHL',br.ReferrerType) referrer_type,
    ROUND(DATEDIFF(CURRENT_DATE, c.Customer_DOB) /365) cust_age,
    c.VehicleCategory vehicle_category,
    ((CASE WHEN ii.SettledTotal > ii.InvoiceTotal THEN ii.InvoiceTotal ELSE ii.SettledTotal END) / ii.InvoiceTotal) yield_perc
FROM insuranceinvoice ii
LEFT JOIN customer c USING (CustomerID)
LEFT JOIN branchreferrer br ON c.ReferrerID = br.ReferrerID
LEFT JOIN lookuplicensecategory lc ON lc.LicenseCategoryID = c.License_Category
LEFT JOIN (SELECT 
               *,
               ROW_NUMBER() OVER(PARTITION BY postcode ORDER BY population DESC) seq
           FROM aus_postcode_mapping
          ) apm ON apm.postcode = c.Postcode AND apm.seq = 1
LEFT JOIN otherpartydriver opd ON opd.CustomerID = c.CustomerID
LEFT JOIN (SELECT
                CustomerID,
                COUNT(VehiclePhoto) num_photos
           FROM customeraccidentphoto
           GROUP BY 1) dp ON dp.CustomerID = c.CustomerID
WHERE ii.SettledDate IS NOT NULL
AND ii.SettledDate >= DATE_ADD(CURRENT_DATE, INTERVAL -24 month)
AND br.ReferrerType IS NOT NULL;
"""

data = connect_and_fecth(endpoint = mysql_creds['aws_endpoint'],
                  user = mysql_creds['db_user'],
                  password = mysql_creds['password'],
                  db_name = mysql_creds['db_name'],
                  port = mysql_creds['port'],
                  query = Query
                )

# Extracting only the main table columns and preparing the final dataframe.

col_names = get_query_column_names(Query)
subqueries = Parser(Query).subqueries
subquery_results = [get_query_column_names(q) for _, q in subqueries.items()]
all_subquery_cols = []

for result in subquery_results:
    for name in result:
        all_subquery_cols.append(name)

main_table_cols = [name for name in col_names if name not in all_subquery_cols]

df = pd.DataFrame(data=data, columns=main_table_cols)

print(df.info())
