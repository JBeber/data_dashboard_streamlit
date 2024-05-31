import pysftp, os
from secret import pwd
from datetime import date, timedelta
import calendar

# Parse year, month, and day from string in YYYYMMDD format
def parse_date(s):
    year = int(s[:4])
    month = int(s[4:6])
    day = int(s[-2:])

    return date(year, month, day)


hostname = 's-9b0f88558b264dfda.server.transfer.us-east-1.amazonaws.com'
export_id = '151717'

with pysftp.Connection(hostname, 
                       username='VvItalianExperienceExportUser',
                       private_key='C:\\Users\\Jeremiah\.ssh\\vvitalian',
                       private_key_pass=pwd) as sftp:
    
    sftp.chdir(export_id)
    # sftp.get('20240505/ItemSelectionDetails.csv', 
    #          localpath='./ItemSelectionDetails_20240505.csv')

    day_count = 21
    seq = range(day_count)
    start_date = parse_date('20240506')
    for single_date in (start_date + timedelta(n) for n in seq):
        # If the current date is a Monday, create a 'week_ending' folder
        # corresponding to the following Friday,
        # then skip the Monday and add the rest of the data for the week
        # to that folder
        if calendar.day_name[single_date.weekday()] == 'Monday':
            end_date = single_date + timedelta(6)
            end_date_str = date.strftime(end_date, '%Y%m%d')
            folder_name = f'Week_ending_{end_date_str}'
            os.mkdir(folder_name)
            os.chdir(folder_name)
        else:
            date_str = date.strftime(single_date, '%Y%m%d')
            sftp.get(f'{date_str}/ItemSelectionDetails.csv', 
                     localpath=f'./ItemSelectionDetails_{date_str}.csv')

        # After Sunday's data is collected, move back 
        # to the parent directory to begin collection for the next week
        if calendar.day_name[single_date.weekday()] == 'Sunday':
            os.chdir('../')   