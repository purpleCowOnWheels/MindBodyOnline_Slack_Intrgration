import sys, os, pdb, requests, json, easygui, http.client, datetime as dt
from pandas             import DataFrame
from slackclient        import SlackClient
from tabulate           import tabulate
from dateutil.parser    import parse
from collections        import Counter
basePath    = os.path.dirname( __file__ ) #location of this exe file, up 2 directories
sys.path.append( basePath )

# import BasicRequestHelper
from encryption import decrypt

input       = easygui.multenterbox(msg='Fill in values for the fields.', title='MBO-Slack Setup', fields=['MBO Username', 'MBO Password', 'Slack Hashname', 'Slack Hashword'], values=['rebecca.licht', '', 'Owner', 'Barre32019'], callback=None, run=True)
mbo_user    = input[0]
mbo_pw      = input[1]

# slack_user  = 'Owner'
# slack_pw    = 'Barre32019'

slack_user  = input[2]
slack_pw    = input[3]

file    = open(basePath + r'/Credentials/' + slack_user + '.json')
creds   = json.load(file)
creds   = { k: decrypt(slack_pw.encode(), v).decode('utf-8') for k, v in creds.items() }

#MBO Dev Credentials
# site_id     = -99
# mbo_user    = 'Siteowner'
# mbo_pw      = 'apitest1234'

#MBO Production Credentials
site_id = "735015"
api_key = "871010c7fe2c4d31ab68410c3d4b2ce3"

conn    = http.client.HTTPSConnection("api.mindbodyonline.com")

def _authenticate_MBO( user, pw, conn ):
    payload = "{\r\n\t\"Username\": \"" + user + "\",\r\n\t\"Password\": \"" + pw + "\"\r\n}"
    headers = { 'Content-Type': "application/json",
                'Api-Key': api_key,
                'SiteId': site_id,
              }
    conn.request("POST", "/public/v6/usertoken/issue", payload, headers)
    res     = conn.getresponse()
    data    = res.read()
    token   = json.loads( data )['AccessToken']
    return( token )

def execRequest( url_ext, headers, conn, type = "GET" ):
    conn.request(type, url_ext, headers=headers)
    res     = conn.getresponse()
    data    = res.read()
    try:
        return( json.loads(data) )
    except:
        pdb.set_trace()
    
headers =   {
                'Api-Key':          api_key,
                'SiteId':           site_id,
                'authorization':    _authenticate_MBO( mbo_user, mbo_pw, conn ),
                'StartDateTime':    dt.date( 2019, 1, 1 ).strftime("%Y-%m-%d"),
                'EndDateTime':      dt.date.today().strftime("%Y-%m-%d"),
            }

#get attendence by member
#get members
url_ext     = "/public/v6/client/clients"
member_data = execRequest( url_ext, headers, conn, type = "GET" )['Clients']
members     = { x['Id']: x for x in member_data }

#get classes
classes     = execRequest( "/public/v6/class/classes", headers, conn, type = "GET" )['Classes']
class_ids   = [ x['Id'] for x in classes ]

#get visits to today's classes
attendance      = { }
clients         = { }
for class_id in class_ids:
    #get class attendance
    url_ext             = "/public/v6/class/classvisits?classId=" + str(class_id)
    this_attendance     = execRequest( url_ext, headers, conn, type = "GET" )['Class']
    
    #get names of attendees
    url_ext             = "/public/v6/client/clients?ClientIds=" + '&ClientIds='.join( [ x['ClientId'] for x in this_attendance['Visits'] ] )
    this_client_data    = execRequest( url_ext, headers, conn, type = "GET" )['Clients']
    these_clients       = { x['Id']: x for x in this_client_data if x['Id'] is not None }
    clients.update( these_clients )
    
    class_time          = parse(this_attendance['StartDateTime']).strftime('%H:%M')    
    attended            = [ these_clients[x['ClientId']]['LastName'] + ', ' + these_clients[x['ClientId']]['FirstName'] for x in this_attendance['Visits'] if x['SignedIn'] ]
    lateCxl             = [ these_clients[x['ClientId']]['LastName'] + ', ' + these_clients[x['ClientId']]['FirstName'] for x in this_attendance['Visits'] if x['LateCancelled'] ]
    other               = [ these_clients[x['ClientId']]['LastName'] + ', ' + these_clients[x['ClientId']]['FirstName'] for x in this_attendance['Visits'] if not x['SignedIn'] and not x['LateCancelled'] ]

    if( not len( attended ) ): continue
    attendance[class_time + ' | ' + this_attendance['Staff']['LastName']]  = { 'attended': attended, 'lateCxl': lateCxl, 'other': other }

#get prior visits by clients
client_dates        = { }
first_visits        = [ ]
key_visits          = [ 5, 10, 25 ] + [ x for x in range( 50, 5000, 50 ) ]
key_client_visits   = { }
for client_id in clients.keys():
    client_name             = clients[client_id]['LastName'] + ', ' + clients[client_id]['FirstName']
    url_ext                 = "/public/v6/client/clientvisits?StartDate=2019-01-01&ClientId=" + client_id
    client_class_data       = execRequest( url_ext, headers, conn, type = "GET" )
    if( 'Visits' not in client_class_data.keys() ): continue
    client_dates[client_id]     = [ parse(x['StartDateTime']) for x in client_class_data['Visits'] if x['ClientId'] == client_id ]
    visit_n                     = len( client_dates[client_id] )
    if( min( client_dates[client_id] ).date() == dt.date.today() ):
        first_visits.append( client_name )
    elif( visit_n in key_visits ):
        if( visit_n in key_client_visits.keys() ):
            key_client_visits[ visit_n ].append( client_name )
        else:
            key_client_visits[ visit_n ] = [ client_name ]

url_ext         = "/public/v6/sale/sales?StartSaleDateTime=" + dt.date.today().strftime( '%Y-%m-%d' ) + "T00:00:00.00"
sales           = execRequest( url_ext, headers, conn, type = "GET" )['Sales']

#get names of buyers
url_ext         = "/public/v6/client/clients?ClientIds=" + '&ClientIds='.join( [ x['ClientId'] for x in sales ] )
sales_clients   = execRequest( url_ext, headers, conn, type = "GET" )['Clients']
clients.update( { x['Id']: x for x in sales_clients if x['Id'] is not None } )

total_rev   =  sum([ sum( [ y['Amount'] for y in x['Payments'] if (('Gift Card' not in y['Type']) and y['Type'] != 'Account')  ] ) for x in sales ])
client_rev  =  [ ( sum( [ y['Amount'] for y in x['Payments'] if (('Gift Card' not in y['Type']) and y['Type'] != 'Account') ] ), clients[x['ClientId']]['LastName'] + ', ' + clients[x['ClientId']]['FirstName']) for x in sales ]
client_rev.sort( reverse = True )

output_str  = '\nTotal Revenue: $' + str(int(total_rev))
output_str  += '\nTotal Attendance: ' + str(len(clients))
output_str  += '\nNew Attendees: ' + str(len(first_visits))
output_str  += '\n  -' + '\n  -'.join( first_visits )
output_str  += '\n\nTop Purchasers:\n  -' + '\n  -'.join([ x[1] + ': $' + str(int(x[0])) for x in client_rev[:5] ])

output_str  += '\n\nClass Details:'
classes_sorted  = sorted(attendance.keys())
for this_class in classes_sorted:
    this_attendance = attendance[this_class]
    output_str  += '\n' + this_class + ' (' + str( len( this_attendance['attended'] ) ) + ')'
    if( len( this_attendance['lateCxl'] ) ):
        output_str  += '\nLate Cancel:\n  -' + '\n  -'.join(this_attendance['lateCxl'])
    else:
        output_str  += '\n  Late Cancel: None'
    if( len( this_attendance['other'] ) ):
        output_str  += '\nOther:\n  -' + '\n  -'.join(this_attendance['other'])

url = creds['webhook']
sc = SlackClient(creds['OAuth'])
sc.api_call( "chat.postMessage", channel=creds['channel'], text= output_str )
