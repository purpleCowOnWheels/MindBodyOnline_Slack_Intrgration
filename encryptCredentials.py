import base64, easygui, pdb, os, sys, json

basePath    = os.path.dirname( __file__ ) #location of this exe file, up 2 directories
sys.path.append( basePath )

from encryption import encrypt

#https://api.slack.com/apps/AJTARPJ1J/incoming-webhooks?
#https://api.slack.com/apps/AJTARPJ1J/oauth?
input   = easygui.multenterbox(msg='Fill in values for the fields.', title='Slack Credentials', fields=['User', 'Create password', 'Incoming Webhook Slack URL', 'Slack OAuth Token', 'Channel'], values=['Owner', '', 'https://api.slack.com/apps/AJTARPJ1J/incoming-webhooks?', 'xoxp-58**********-63**********-62**********-2e********************', 'CHL2NDBTL'], callback=None, run=True)
user        = input[0]
pw          = input[1].encode('latin-1')

data_to_encrpyt = {
                    'webhook':      input[2],
                    'OAuth':        input[3],
                    'channel':      input[4],
                  }
creds   = { k: encrypt(pw, v.encode('latin-1')) for k, v in data_to_encrpyt.items() }
if( not os.path.exists( basePath + r'/Credentials' ) ):
    os.mkdir( basePath + r'/Credentials' )

file    = open( basePath + r'/Credentials/' + user + '.json', 'w+')
json.dump( creds, file )
file.close()
