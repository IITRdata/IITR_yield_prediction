import pandas as pd
import numpy as np
from preprocessing import Preprocessor
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.ensemble import RandomForestRegressor
from catboost import CatBoostRegressor



# Reading the dataset.

processor = Preprocessor(model_name='Recovery Yield')
df = pd.read_csv('train.csv')
cleaned_df = processor.format_table_attrs(dataset=df)
cat_cols = [col for col in cleaned_df.columns if cleaned_df[col].dtype in ('category', 'str')]

# Splitting the dataset.

X = cleaned_df.drop('yield_perc', axis = 1)
y = cleaned_df['yield_perc']

X_train, X_test, y_train, y_test = train_test_split(X,y, test_size=.20, random_state = 5)

encoded_train_x = processor.encode_df(
    x=X,
    train_set = X_train,
    is_train = True,
    categorical_cols = cat_cols)

# Grid Search CV - RF.

# rfr = RandomForestRegressor(random_state = 6)

# param_grid = {
#     'n_estimators': np.arange(100, 601, 100),
#     'max_depth': np.arange(2,10,1),
#     'min_samples_split': np.arange(2,5,1),
#     'min_samples_leaf': np.arange(1,4,1),
#     'ccp_alpha': [0, 0.001, 0.01]
# }

# gs = GridSearchCV(
#     estimator=rfr,
#     param_grid=param_grid,
#     cv=3,
#     scoring='neg_root_mean_squared_error',
#     n_jobs=-1,
#     return_train_score=True
# )

# gs.fit(encoded_train_x, y_train)
# best_model = gs.best_params_
# best_score = gs.best_score_ * -1

# print(f"Best params: {best_model}\nBest Score: {(best_score * 100):.2f}")

# Grid Search Cat Boost.

cat_reg = CatBoostRegressor(
    loss_function = 'RMSE',
    random_seed = 10,
    thread_count = -1,
    verbose=0)

cat_params = {
    'iterations': np.arange(200,1501, 100),
    'learning_rate': np.arange(0.01, 1, .01 ),
    'depth': np.arange(6,13,1),
    'loss_function': ['RMSE']
}

cat_gs = GridSearchCV(
    estimator=cat_reg,
    param_grid=cat_params,
    cv=3,
    scoring='neg_root_mean_squared_error',
    n_jobs=-1
).fit(X_train, y_train, cat_features = cat_cols)

best_params = cat_gs.best_params_
best_score = cat_gs.best_score_ * -1

print(f"Best Params: {best_params}\nBest Score: {best_score:.2f}")