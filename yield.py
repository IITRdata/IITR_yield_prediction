import pandas as pd
import numpy as np
import mysql.connector
from mysql.connector import Error
from credentials import mysql_creds
from sql_metadata import Parser
import matplotlib.pyplot as plt

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


def main_table_col_names(query: str):
    """Filters the main table name from the query

    :param query: The actual query reuired to extract data.
    :result: A list containing the column names to be used in the main table.

    >>> main_table_col_names(SELECT name, age, gender FROM customer)
    ['name', 'age', 'gender']
    """

    col_names = get_query_column_names(Query)
    subqueries = Parser(Query).subqueries
    subquery_results = [get_query_column_names(q) for _, q in subqueries.items()]
    all_subquery_cols = []

    for result in subquery_results:
        for name in result:
            all_subquery_cols.append(name)

    main_table_cols = [name for name in col_names if name not in all_subquery_cols]

    return main_table_cols

def format_table_attrs(dataset: pd.DataFrame):
    """Set's the correct data types for each column.
     
    :param dataset: The pandas dataset to be cleaned.
    :result: A new dataset with same column names and correct data types.

    >>> format_table_attrs(dataset=df)

    <class 'pandas.DataFrame'>
    RangeIndex: 18237 entries, 0 to 18236
    Data columns (total 17 columns):
    #   Column                      Non-Null Count  Dtype   
    ---  ------                      --------------  -----   
    0   naf_region                  18237 non-null  category
    1   naf_economic_score          18237 non-null  float32 
    2   naf_professional_score      18237 non-null  float32 
    3   naf_is_priority_cust        18237 non-null  int8    
    4   naf_has_insurance           18237 non-null  int8
    ...
    """

    attr_mapping = {
        'naf_region': 'category',
        'naf_economic_score': np.float32,
        'naf_professional_score': np.float32,
        'naf_is_priority_cust': np.int8,
        'naf_has_insurance': np.int8,
        'naf_vehicle_age': np.int16,
        'naf_age': np.int16,
        'naf_provided_rego_doc': np.int8,
        'af_has_insurance': np.int8,
        'af_provided_claim_num': np.int8,
        'af_addr_on_record': np.int8,
        'af_has_contact': np.int8,
        'naf_provided_damage_photos': np.int8,
        'referrer_type': 'category',
        'naf_vehicle_category': 'category',
        'naf_vehicle_type': 'category',
        'naf_yearend_checkin': np.int8,
        'yield_perc': np.float16
    }

    df = dataset.dropna(axis=0)
    cleaned_df = df.astype(attr_mapping)

    return cleaned_df

##################### Query for Data Extraction ############################

Query = """SELECT
    apm.region_mapping naf_region,
    CAST(apm.resource_score AS DECIMAL(6,4)) naf_economic_score,
    CAST(apm.education_and_occupation_score AS DECIMAL(6,4)) naf_professional_score,
    IF(c.CustomerPriority = 'Priority', 1,0) naf_is_priority_cust,
    IF(ca.InsuranceCompany IS NOT NULL, 1,0) naf_has_insurance,
    (YEAR(CURDATE()) - c.VehicleYear) naf_vehicle_age,
    ROUND(DATEDIFF(CURRENT_DATE, c.Customer_DOB) /365) naf_age,
    IF(cvr.VehicleRegistrationDocument IS NOT NULL,1,0) naf_provided_rego_doc,
    IF(dp.num_photos >= 1, 1,0) naf_provided_damage_photos,
    c.VehicleCategory naf_vehicle_category,
    ml.VehicleType naf_vehicle_type,
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
LEFT JOIN lookupvehiclemasterlist ml ON ml.VehicleModelID = c.VehicleModelID
WHERE ii.SettledDate IS NOT NULL
AND ii.SettledDate >= DATE_ADD(CURRENT_DATE, INTERVAL -36 month)
AND br.ReferrerType IS NOT NULL
AND c.AgreementTypeID = 1
AND ml.VehicleType IS NOT NULL;
"""

data = connect_and_fecth(endpoint = mysql_creds['aws_endpoint'],
                  user = mysql_creds['db_user'],
                  password = mysql_creds['password'],
                  db_name = mysql_creds['db_name'],
                  port = mysql_creds['port'],
                  query = Query
                )


# original dataframe.

df = pd.DataFrame(data=data, columns=main_table_col_names(query=Query))

# Data Preprocessing

cleaned_df = format_table_attrs(dataset=df)
cleaned_df['naf_age_class'] = pd.cut(
    x=cleaned_df['naf_age'],
    bins=[min(cleaned_df['naf_age']), 30, 60, 80, max(cleaned_df['naf_age'])], 
    labels=['<=30', '31-60', '61-80', '80+'],
    include_lowest=True
    )

cleaned_df['naf_vehicle_age_class'] = pd.cut(
    x=cleaned_df['naf_vehicle_age'],
    bins=[min(cleaned_df['naf_vehicle_age']), 5, 10, 15, max(cleaned_df['naf_vehicle_age'])] ,
    labels=['<=5', '6-10', '11-15', '15+'],
    include_lowest=True
)

