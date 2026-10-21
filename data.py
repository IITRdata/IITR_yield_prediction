from preprocessing import Preprocessor
from credentials import mysql_creds
import pandas as pd
import shap
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

# initializing the preprocessing class.

processor = Preprocessor(model_name='Yield Prediction')

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

data = processor.connect_and_fetch(endpoint = mysql_creds['aws_endpoint'],
                  user = mysql_creds['db_user'],
                  password = mysql_creds['password'],
                  db_name = mysql_creds['db_name'],
                  port = mysql_creds['port'],
                  query = Query
                )


# original dataframe.

df = pd.DataFrame(
    data = data,
    columns = processor.main_table_col_names(query=Query)
    )

# Data Preprocessing

cleaned_df = processor.format_table_attrs(dataset=df)

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

X = cleaned_df.drop('yield_perc', axis = 1)
y = cleaned_df['yield_perc']

X_train, X_test, y_train, y_test = train_test_split(X,y, test_size=0.2, random_state = 0)

X_train_encoded = processor.encode_df(
    x = X,
    train_set = X_train,
    is_train = True,
    categorical_cols = cat_cols)

# Feature Selection using SHAP.

rf_reg = RandomForestRegressor(
    n_estimators = 300,
    random_state = 1
).fit(X_train_encoded, y_train)

samples100 = shap.utils.sample(X_train_encoded, 100)
explainer = shap.Explainer(rf_reg, samples100)
explanation = explainer(samples100)
feature_values = explanation.abs.mean(0)
final_vals = dict(zip(X_train_encoded.columns, feature_values.values))

selected_predictors = processor.key_columns(
    x = X,
    current_vals = final_vals
    )
selected_predictors.append('yield_perc')

# saving the filtered dataframe.

cleaned_df[selected_predictors].to_csv('model_data.csv', index = False)