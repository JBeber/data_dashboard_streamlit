import pysftp, os, sys
# from secret import pwd, hostname, export_id
from datetime import date, timedelta
from calendar import day_name
import streamlit as st
import pandas as pd



# def collect_data(args):
#     with pysftp.Connection(st.secrets['hostname'], 
#                         username=st.secrets['username'],
#                         private_key=st.secrets['private_key'],
#                         private_key_pass=st.secrets['pwd']) as sftp:
        
#         sftp.chdir(st.secrets['export_id'])

#         day_count = int(args[2])
#         seq = range(day_count)
#         start_date = parse_date(args[1])

#         for single_date in (start_date + timedelta(n) for n in seq):
#             # If the current date is a Monday, create a 'week_ending' folder
#             # corresponding to the following Friday,
#             # then skip the Monday and collect the rest of the data 
#             # for the week to that folder
#             if day_name[single_date.weekday()] == 'Monday':
#                 end_date = single_date + timedelta(6)
#                 end_date_str = date.strftime(end_date, '%Y%m%d')
#                 folder_name = f'Week_ending_{end_date_str}'
#                 os.mkdir(folder_name)
#                 os.chdir(folder_name)
#             else:
#                 date_str = date.strftime(single_date, '%Y%m%d')
#                 sftp.get(f'{date_str}/ItemSelectionDetails.csv', 
#                         localpath=f'./ItemSelectionDetails_{date_str}.csv')

#             # After Sunday's data is collected, move back 
#             # to the parent directory to begin collection for the next week
#             if day_name[single_date.weekday()] == 'Sunday':
#                 os.chdir('../')


            
    # TODO: store data remotely in a subdirectory accessible by Streamlit
        # for date_str in str_dt_lst:
        #     sftp.chdir(f'./{date_str}')
        #     sftp.get('./AllItemsReport.csv', 
        #                         localpath=f'../Daily_Data/AllItemsReport_{date_str}.csv')
        #     sftp.chdir('../')
    

# Collect all available week ending dates from subdirectories 
# in the main directory and return the five most recent weeks
# as a list of directory names
def get_five_weeks_dirs(data_dir):
    # Get today's date
    today = date.today()

    # Get a list of relevant directory names
    dir_lst = [name for name in os.listdir(data_dir)]
    
    # Initialize a list to store directory names for return
    returned_dirs = []

    for dir_name in dir_lst:
        # Collect date from the current directory name
        date_str = ''.join(filter(str.isdigit, dir_name))

        # Date object for directory name currently being processed
        current_dir_date = parse_date(date_str)

        five_weeks = timedelta(weeks=5)

        if today - current_dir_date <= five_weeks:
            returned_dirs.append(dir_name)

    return returned_dirs

if __name__ == '__main__':
    collect_data(sys.argv)