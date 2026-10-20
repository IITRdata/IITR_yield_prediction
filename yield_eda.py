import pandas as pd
import numpy as np
import mysql.connector
from mysql.connector import Error
from credentials import mysql_creds
from sql_metadata import Parser
import matplotlib.pyplot as plt
from sklearn.preprocessing import OneHotEncoder
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
import regex as re
import seaborn as sns
import shap

# function definitions.

def connect_and_fetch (endpoint: str,
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
        'naf_vehicle_class': 'category',
        'naf_yearend_checkin': np.int8,
        'yield_perc': np.float16
    }

    df = dataset.dropna(axis=0)
    cleaned_df = df.astype(attr_mapping)

    return cleaned_df


def encoded_df(
        x: pd.DataFrame,
        train_set: pd.DataFrame,
        test_set: pd.DataFrame,
        is_train: bool,
        categorical_cols: list):

    encoder = OneHotEncoder(drop ='first',
                            handle_unknown = 'error',
                            sparse_output = False,
                            dtype = np.int8
                        )
    
    all_columns = set(x.columns)
    cat_columns = set(categorical_cols)
    num_cols = list(all_columns.difference(cat_columns))

    encoder.fit(train_set[categorical_cols]) 

    # processing the training dataset.

    if is_train:
        encoded_df =  pd.DataFrame(
            data = encoder.transform(train_set[categorical_cols]),
            columns=encoder.get_feature_names_out(),
            index = train_set.index)

        X_train_encoded = pd.concat([train_set[num_cols], encoded_df], axis = 1)

        return X_train_encoded
    
    else:
        encoded_df = pd.DataFrame(
            data = encoder.transform(test_set[categorical_cols]),
            columns = encoder.get_feature_names_out(),
            index = test_set.index)

        X_test_encoded = pd.concat([test_set[num_cols, encoded_df]], axis = 1)

        return X_test_encoded

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
    model_class. vehicle_class naf_vehicle_class,
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
LEFT JOIN (
	SELECT
        t1.VehicleModelID,
        t1.daily_hire_rate,
        CASE
            WHEN t1.percentile <= 0.33 THEN 'Entry'
            WHEN t1.percentile <= 0.67 THEN 'Medium'
            ELSE 'Premium'
        END AS vehicle_class
    FROM (
        SELECT
            ml.VehicleModelID,
            COALESCE(ml.VehicleCustomRate, vt.VehicleRateMinimum) AS daily_hire_rate,
            PERCENT_RANK() OVER (
                ORDER BY COALESCE(ml.VehicleCustomRate, vt.VehicleRateMinimum)
            ) AS percentile
        FROM lookupvehiclemasterlist ml
        LEFT JOIN lookupvehicletype vt ON  ml.ChargeSubType = vt.ChargeSubType 
        AND ml.VehicleType = vt.VehicleType) AS t1) AS model_class ON model_class.VehicleModelID = c.VehicleModelID
WHERE ii.SettledDate IS NOT NULL
AND ii.SettledDate >= DATE_ADD(CURRENT_DATE, INTERVAL -36 month)
AND br.ReferrerType IS NOT NULL
AND c.AgreementTypeID = 1
AND ml.VehicleType IS NOT NULL;
"""

data = connect_and_fetch(endpoint = mysql_creds['aws_endpoint'],
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

cleaned_df.drop(['naf_vehicle_age', 'naf_age'], axis = 1, inplace = True)
cat_cols = [col for col in cleaned_df.columns if cleaned_df[col].dtype == 'category'] # cols for one-hot encoding

# Splitting the dataset.

X = cleaned_df.drop('yield_perc', axis= 1).copy()
y = cleaned_df['yield_perc'].copy()
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size = .20, random_state = 10)

encoded_train_X = encoded_df(
    x = X, 
    train_set = X_train,
    test_set = X_test,
    is_train = True,
    categorical_cols = cat_cols)

# Understanding predictor contribution.

rf_reg= RandomForestRegressor(n_estimators = 300, random_state = 5).fit(encoded_train_X, y_train)
mapped_importances = dict(zip( encoded_train_X, rf_reg.feature_importances_))

feature_importances = {}

for col in X.columns:
    pattern = re.compile(rf"^{re.escape(col)}(_.+)?$")

    if col not in cat_cols:
        feature_importances[col] = mapped_importances[col]

    else:
        col_imp = sum([v for k, v in mapped_importances.items() if pattern.match(k)])
        feature_importances[col] = col_imp

sorted_imp_values = dict(sorted(feature_importances.items(),
                                key = lambda item: item[1]))

fig = plt.figure(figsize=(10,6))
plt.barh(y = sorted_imp_values.keys(), 
         width = sorted_imp_values.values(), 
         align ='center')
plt.xlabel("Feature Importance (%)")
plt.title("Random Forest Feature Importance")
plt.tight_layout()
plt.show()

# Permutation Importance

results = permutation_importance(
    rf_reg,
    encoded_train_X, y_train,
    n_repeats = 5,
    random_state = 4,
    scoring='neg_root_mean_squared_error')

perm_importances = dict(zip(encoded_train_X.columns, results.importances_mean))

pi_feature_scores = {}

for col in X.columns:
    pattern = re.compile(rf"^{re.escape(col)}(_.+)?$")

    if col not in cat_cols:
        pi_feature_scores[col] = perm_importances[col]

    else:
        col_imp = sum([v for k, v in perm_importances.items() if pattern.match(k)])
        pi_feature_scores[col] = col_imp

sorted_pi_values = dict(sorted(pi_feature_scores.items(),
                                key = lambda item: item[1]))


plt.barh(y = sorted_pi_values.keys(), 
         width = sorted_pi_values.values(), 
         align ='center')
plt.xlabel("Feature Importance (%)")
plt.title("Permutation Feature Importance")
plt.tight_layout()
plt.show()


# SHAP gloabl importance.
samples = shap.utils.sample(encoded_train_X, 1000)
explainer = shap.Explainer(rf_reg, samples)
explanation = explainer(samples)
mean_values = explanation.abs.mean(0)

final_vals = dict(zip(encoded_train_X.columns, mean_values.values))

shap_feature_contribution = {}

for col in X.columns:
    pattern = re.compile(rf"^{re.escape(col)}(_.+)?$")

    if col not in cat_cols:
        shap_feature_contribution[col] = final_vals[col]

    else:
        col_imp = sum([v for k, v in final_vals.items() if pattern.match(k)])
        shap_feature_contribution[col] = col_imp

sorted_shap_values = dict(sorted(shap_feature_contribution.items(),
                                key = lambda item: item[1]))


plt.figure(figsize=(12,6))
ax = sns.barplot(
            x = sorted_shap_values.values(),
            y = sorted_shap_values.keys(),
            color='r'
        )
ax.bar_label(ax.containers[0], fmt ='%.4f',label_type = 'edge')
plt.xlabel("Mean SHAP Values")
plt.title("SHAP Feature Importance")
plt.tight_layout()
plt.show()


