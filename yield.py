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
    apm.region_mapping naf_region,
    CAST(apm.resource_score AS DECIMAL(6,4)) naf_economic_score,
    CAST(apm.education_and_occupation_score AS DECIMAL(6,4)) naf_professional_score,
    IF(c.CustomerPriority = 'Priority', 1,0) naf_is_priority_cust,
    IF(ca.InsuranceCompany IS NOT NULL, 1,0) naf_has_insurance,
    c.VehicleYear naf_vehicle_year,
    ROUND(DATEDIFF(CURRENT_DATE, c.Customer_DOB) /365) naf_age,
    IF(cvr.VehicleRegistrationDocument IS NOT NULL,1,0) naf_provided_rego_doc,
    IF(dp.num_photos >= 1, 1,0) naf_provided_damage_photos,
    c.VehicleCategory naf_vehicle_category,
    IF(MONTH(DATE_ADD(c.CheckoutDateTime, INTERVAL c.HireDuration DAY)) IN (12, 1),1,0) naf_yearend_checkin,
    IF(opd.OPD_InsuranceIndicator = 'Y',1,0) af_has_insurance,
    IF(opd.OPD_InsuranceClaimNo IS NOT NULL,1,0) af_provided_claim_num,
    IF(opd.OPD_Address1 IS NOT NULL AND opd.OPD_Postcode is NOT NULL AND opd.OPD_State
    IS NOT NULL, 1,0) af_addr_on_record,
    IF(opd.OPD_MobileAvailable = 'Y', 1,0) af_has_contact,
    IF(br.ReferrerID=180,'ACHL',br.ReferrerType) referrer_type,
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
LEFT JOIN customerapplicant ca ON ca.CustomerInboundID = c.CustomerInboundID
LEFT JOIN customervehiclerepair cvr ON cvr.CustomerID = c.CustomerID
WHERE ii.SettledDate IS NOT NULL
AND ii.SettledDate >= DATE_ADD(CURRENT_DATE, INTERVAL -24 month)
AND br.ReferrerType IS NOT NULL
AND c.AgreementTypeID = 1;
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

# Data cleaning and preprocessing.

attr_mapping = {
    'naf_region': 'category',
    'naf_economic_score': np.float32,
    'naf_professional_score': np.float32,
    'naf_is_priority_cust': np.int8,
    'naf_has_insurance': np.int8,
    'naf_vehicle_year': np.int16,
    'naf_age': np.int16,
    'naf_provided_rego_doc': np.int8,
    'af_has_insurance': np.int8,
    'af_provided_claim_num': np.int8,
    'af_addr_on_record': np.int8,
    'af_has_contact': np.int8,
    'naf_provided_damage_photos': np.int8,
    'referrer_type': 'category',
    'naf_vehicle_category': 'category',
    'naf_yearend_checkin': np.int8,
    'yield_perc': np.float16
}

df = df.dropna(axis=0)
cleaned_df = df.astype(attr_mapping)

print(cleaned_df.info())