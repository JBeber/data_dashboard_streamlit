import pysftp, shutil, os
from secret import pwd
from datetime import date, timedelta

hostname = 's-9b0f88558b264dfda.server.transfer.us-east-1.amazonaws.com'
export_id = '151717'

with pysftp.Connection(hostname, 
                       username='VvItalianExperienceExportUser',
                       private_key='C:\\Users\\Jeremiah\.ssh\\vvitalian',
                       private_key_pass=pwd) as sftp:
    
    sftp.chdir(export_id)
    sftp.get('20240505/ItemSelectionDetails.csv', localpath='./ItemSelectionDetails_20240505.csv')




    # day_count = 21
    # start_date = '20240506'
    # seq = range(day_count)
    # for single_date in (start_date + timedelta(n) for n in seq):
    #     if seq % 7 == 0:
    #         end_date = single_date
    #         os.mkdir('')

    