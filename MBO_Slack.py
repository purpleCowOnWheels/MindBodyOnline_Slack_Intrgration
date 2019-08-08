import sys, os, pdb, requests, json, easygui, http.client, datetime as dt
from pandas             import DataFrame
from slackclient        import SlackClient
from dateutil.parser    import parse
from collections        import Counter, abc
basePath    = os.path.dirname( __file__ ) #location of this exe file, up 2 directories
sys.path.append( basePath )

from encryption import decrypt

#prepare arguments; make possible to run locally or as batch script
default_vals    = ['rebecca.licht', '', 'Owner', 'Barre32019', dt.date.today().strftime('%Y-%m-%d')]
if( len( sys.argv ) == 1 ):
    input       = easygui.multenterbox(msg='Fill in values for the fields.', title='MBO-Slack Setup', fields=['MBO Username', 'MBO Password', 'Slack Hashname', 'Slack Hashword', 'Report Date'], values=default_vals, callback=None, run=True)
    mbo_user    = input[0]
    mbo_pw      = input[1]

    slack_user  = input[2]
    slack_pw    = input[3]
    asOf        = input[4]
else:
    mbo_user    = default_vals[0]
    mbo_pw      = sys.argv[1]
    slack_user  = default_vals[2]
    slack_pw    = default_vals[3]
    asOf        = default_vals[4]

#decrypt various credentials
file    = open(basePath + r'/Credentials/' + slack_user + '.json')
creds   = json.load(file)
creds   = { k: decrypt(slack_pw.encode(), v).decode('utf-8') for k, v in creds.items() }
pdb.set_trace()
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

def uniqList( k ):
    if( isinstance( k, abc.ValuesView ) or isinstance( k, abc.KeysView ) ): k = [ x for x in k ]
    if( not( len(k) ) ): return( [ ] )
    if( isinstance( k[0], list ) ):
        return( list(set( [item for sublist in k for item in sublist] ) ) )
    else:
        return( list(set(k) ) )

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
print( '  >> Getting classes on ' + asOf + '...' )
classes     = execRequest( "/public/v6/class/classes?startdatetime=" + asOf + '&enddatetime=' + asOf, headers, conn, type = "GET" )['Classes']
classes     = { x['Id']: x for x in classes }
class_ids   = [ x['Id'] for x in classes.values() if x['ClassDescription']['Name'] in [ 'barre3', 'Play Lounge'] ]

#get visits to today's classes
attendance      = { }
clients         = { }
print( '  >> Getting attendance for class:' )
for class_id in class_ids:
    class_details   = classes[class_id]
    class_time      = parse(class_details['StartDateTime']).strftime('%H:%M')
    class_type      = class_details['ClassDescription']['Name']
    print( '    ++ ' + class_time + ' (' + class_type + ')' )
    
    #get class attendance
    url_ext             = "/public/v6/class/classvisits?classId=" + str(class_id)
    this_attendance     = execRequest( url_ext, headers, conn, type = "GET" )['Class']
    
    #get names of attendees
    url_ext             = "/public/v6/client/clients?ClientIds=" + '&ClientIds='.join( [ x['ClientId'] for x in this_attendance['Visits'] ] )
    this_client_data    = execRequest( url_ext, headers, conn, type = "GET" )['Clients']
    these_clients       = { x['Id']: x for x in this_client_data if x['Id'] is not None }
    
    attended            = [ these_clients[x['ClientId']]['LastName'].title() + ', ' + these_clients[x['ClientId']]['FirstName'].title() for x in this_attendance['Visits'] if x['SignedIn'] ]
    lateCxl             = [ these_clients[x['ClientId']]['LastName'].title() + ', ' + these_clients[x['ClientId']]['FirstName'].title() for x in this_attendance['Visits'] if x['LateCancelled'] ]
    other               = [ these_clients[x['ClientId']]['LastName'].title() + ', ' + these_clients[x['ClientId']]['FirstName'].title() for x in this_attendance['Visits'] if not x['SignedIn'] and not x['LateCancelled'] ]

    if( not len( attended ) ): continue
    attended_ids        = [ x['ClientId'] for x in this_attendance['Visits'] if x['SignedIn'] ]
    clients.update( { client_id: client_data for client_id, client_data in these_clients.items() if client_id in attended_ids } )
    attendance[class_time + ' | ' + this_attendance['Staff']['LastName']]  = { 'attended': attended, 'lateCxl': lateCxl, 'other': other, 'classType': class_type }

#get prior visits by clients
client_dates        = { }
first_visits        = [ ]
key_visits          = [ 5, 10, 25 ] + [ x for x in range( 50, 5000, 50 ) ]
key_client_visits   = { }
print( '  >> Getting prior visits for client: ' )
for client_id in clients.keys():
    client_name             = clients[client_id]['LastName'].title() + ', ' + clients[client_id]['FirstName'].title()
    print( '    ++ ' + client_name )

    url_ext                 = "/public/v6/client/clientvisits?StartDate=2019-01-01&enddate=" + asOf + "&ClientId=" + client_id
    client_class_data       = execRequest( url_ext, headers, conn, type = "GET" )
    if( 'Visits' not in client_class_data.keys() ): continue
    client_dates[client_id]     = [ parse(x['StartDateTime']) for x in client_class_data['Visits'] if x['ClientId'] == client_id ]
    visit_n                     = len( client_dates[client_id] )
    if( min( client_dates[client_id] ).date() == dt.date.today() ):
        first_visits.append( client_name )
        print( '      -- New client! Welcome!!' )
    elif( visit_n in key_visits ):
        print( '      -- Key visit ' + str( visit_n ) + '!' )
        if( visit_n in key_client_visits.keys() ):
            key_client_visits[ visit_n ].append( client_name )
        else:
            key_client_visits[ visit_n ] = [ client_name ]
url_ext         = "/public/v6/sale/sales?StartSaleDateTime=" + asOf + "T00:00:00.00&EndSaleDateTime=" + asOf + "T23:59:59.99"
sales           = execRequest( url_ext, headers, conn, type = "GET" )['Sales']

#get names of buyers
url_ext         = "/public/v6/client/clients?ClientIds=" + '&ClientIds='.join( [ x['ClientId'] for x in sales ] )
sales_clients   = execRequest( url_ext, headers, conn, type = "GET" )['Clients']
sales_clients   = { x['Id']: x for x in sales_clients if x['Id'] is not None }

# clients.update( { x['Id']: x for x in sales_clients if x['Id'] is not None } )

total_rev   =  sum([ sum( [ y['Amount'] for y in x['Payments'] if (('Gift Card' not in y['Type']) and y['Type'] != 'Account')  ] ) for x in sales ])
client_rev  =  [ ( sum( [ y['Amount'] for y in x['Payments'] if (('Gift Card' not in y['Type']) and y['Type'] != 'Account') ] ), sales_clients[x['ClientId']]['LastName'].title() + ', ' + sales_clients[x['ClientId']]['FirstName'].title()) for x in sales if x['ClientId'] != '0' ]
client_rev.sort( reverse = True )
client_rev  = [ x for x in client_rev if x[0] > 0 ]

output_str  = '##############\n# ' + asOf + ' #\n##############'
output_str  += '\nTotal Revenue: $' + str(int(total_rev))
output_str  += '\nTotal Attendance: ' + str(len(clients))
output_str  += '\nNew Attendees: ' + str(len(first_visits))
if( len( first_visits ) ): output_str  += '\n  -' + '\n  -'.join( first_visits )
output_str  += '\n\nTop Purchasers:'
if( len( client_rev ) ): output_str += '\n  -' + '\n  -'.join([ x[1] + ': $' + str(int(x[0])) for x in client_rev[:10] ])

output_str  += '\n\nClass Details:'
classes_sorted  = sorted(attendance.keys())
for this_class in classes_sorted:
    this_attendance = attendance[this_class]
    output_str  += '\n' + this_class + ' (' + str( len( this_attendance['attended'] ) ) + ')'
    if( len( this_attendance['lateCxl'] ) ):
        output_str  += '\nLate Cancel:\n  -' + '\n  -'.join(this_attendance['lateCxl'])
    if( len( this_attendance['other'] ) ):
        output_str  += '\nOther:\n  -' + '\n  -'.join(this_attendance['other'])

if( len( key_client_visits ) ):
    output_str  += '\n\n...Key Visits...'
    
    for visit_n in sorted(key_client_visits.keys()):
        output_str  += '\n' + str( visit_n ) + ':\n  -' + '\n  -'.join( key_client_visits[visit_n] )

url = creds['webhook']
sc  = SlackClient(creds['OAuth'])
sc.api_call( "chat.postMessage", channel=creds['channel'], text= output_str )
