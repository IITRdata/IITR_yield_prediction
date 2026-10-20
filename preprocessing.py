import pandas as pd
import numpy as np
import mysql.connector
from mysql.connector import Error
from sql_metadata import Parser
from sklearn.preprocessing import OneHotEncoder

class Preprocessor:
    def __init__(self, model_name: str):
        self.model = model_name

    def connect_and_fetch (
            sef,
            endpoint: str,
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

    def get_query_column_names(self, query: str):
        parser = Parser(query)

        return parser.output_columns

    def main_table_col_names(self, query: str):

        """Filters the main table name from the query

        :param query: The actual query reuired to extract data.
        :result: A list containing the column names to be used in the main table.

        >>> main_table_col_names(SELECT name, age, gender FROM customer)
        ['name', 'age', 'gender']
        """

        col_names = self.get_query_column_names(query = query)
        subqueries = Parser(query).subqueries
        subquery_results = [self.get_query_column_names(q) for _, q in subqueries.items()]
        all_subquery_cols = []

        for result in subquery_results:
            for name in result:
                all_subquery_cols.append(name)

        main_table_cols = [name for name in col_names if name not in all_subquery_cols]

        return main_table_cols

    def format_table_attrs(self, dataset: pd.DataFrame):

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
        self,
        x: pd.DataFrame,
        train_set: pd.DataFrame,
        is_train: bool,
        categorical_cols: list,
        test_set: pd.DataFrame | None = None):

        encoder = OneHotEncoder(
            drop ='first',
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