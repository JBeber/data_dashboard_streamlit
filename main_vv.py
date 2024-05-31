import pysftp, os, sys
from secret import pwd, hostname, export_id
from datetime import date, timedelta
from calendar import day_name

# Parse year, month, and day from string in YYYYMMDD format
def parse_date(s):
    year = int(s[:4])
    month = int(s[4:6])
    day = int(s[-2:])

    return date(year, month, day)

def main(args):
    with pysftp.Connection(hostname, 
                        username='VvItalianExperienceExportUser',
                        private_key='C:\\Users\\Jeremiah\.ssh\\vvitalian',
                        private_key_pass=pwd) as sftp:
        
        sftp.chdir(export_id)

        day_count = int(args[2])
        seq = range(day_count)
        start_date = parse_date(args[1])

        for single_date in (start_date + timedelta(n) for n in seq):
            # If the current date is a Monday, create a 'week_ending' folder
            # corresponding to the following Friday,
            # then skip the Monday and add the rest of the data for the week
            # to that folder
            if day_name[single_date.weekday()] == 'Monday':
                end_date = single_date + timedelta(6)
                end_date_str = date.strftime(end_date, '%Y%m%d')
                folder_name = f'{cwd}\\Week_ending_{end_date_str}'
                os.mkdir(folder_name)
                os.chdir(folder_name)
            else:
                date_str = date.strftime(single_date, '%Y%m%d')
                sftp.get(f'{date_str}/ItemSelectionDetails.csv', 
                        localpath=f'./ItemSelectionDetails_{date_str}.csv')

            # After Sunday's data is collected, move back 
            # to the parent directory to begin collection for the next week
            if day_name[single_date.weekday()] == 'Sunday':
                os.chdir('../')


if __name__ == '__main__':
    main(sys.argv)