import pandas as pd

# Set operatings days for date range generation
vv_weekmask = 'Tue Wed Thu Fri Sat Sun'
vv_business_days = pd.offsets.CustomBusinessDay(weekmask=vv_weekmask)