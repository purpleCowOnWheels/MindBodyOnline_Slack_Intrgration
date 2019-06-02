import sys, os, pdb, requests, json, easygui, http.client, datetime as dt
from pandas             import DataFrame
from slackclient        import SlackClient
from tabulate           import tabulate
from dateutil.parser    import parse
from collections        import Counter
basePath    = os.path.dirname( __file__ ) #location of this exe file, up 2 directories
sys.path.append( basePath )

import BasicRequestHelper
from encryption import decrypt

input       = easygui.multenterbox(msg='Fill in values for the fields.', title='MBO-Slack Setup', fields=['MBO Username', 'MBO Password', 'Slack Hashname', 'Slack Hashword'], values=['rebecca.licht', '', 'Owner', 'Barre32019'], callback=None, run=True)
mbo_user    = input[0]
mbo_pw      = input[1]
slack_user  = input[2]
slack_pw    = input[3]

file    = open(basePath + r'/Credentials/' + slack_user + '.json')
creds   = json.load(file)
creds   = { k: decrypt(slack_pw.encode(), v).decode('utf-8') for k, v in creds.items() }

# user    = 'rebecca.licht'
# pw      = 'M@gicDr@g0n'
api_key = "871010c7fe2c4d31ab68410c3d4b2ce3"
site_id = "735015"
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
                # 'StartDateTime':    dt.date.today().strftime("%Y-%m-%d"),
                # 'EndDateTime':      dt.date.today().strftime("%Y-%m-%d"),
            }

#get attendence by member
#get members
url_ext     = "/public/v6/client/clients"
member_data = execRequest( url_ext, headers, conn, type = "GET" )['Clients']
members     = { x['Id']: x for x in member_data }

# client_dates    = { }
# for client in clients:
    # print( '  >> Getting class attendance for ' + client )
    # url_ext                 = "/public/v6/class/clientvisits?ClientId="+str(client)
    # client_class_data       = execRequest( url_ext, headers, conn, type = "GET" )
    # client_dates[client]    = [ parse(x['StartDateTime']) for x in client_class_data['Classes'] ]
# pdb.set_trace()

#get classes
classes     = execRequest( "/public/v6/class/classes", headers, conn, type = "GET" )['Classes']
class_ids   = [ x['Id'] for x in classes ]

#get visits to today's classes
attendance      = { }
for class_id in class_ids:
    url_ext             = "/public/v6/class/classvisits?classId=" + str(class_id)
    this_attendance     = execRequest( url_ext, headers, conn, type = "GET" )['Class']
    
    url_ext             = "/public/v6/client/clients?ClientIds=" + '&ClientIds='.join( [ x['ClientId'] for x in this_attendance['Visits'] ] )
    this_client_data    = execRequest( url_ext, headers, conn, type = "GET" )['Clients']
    these_clients       = { x['Id']: x for x in this_client_data }

    class_time          = parse(this_attendance['StartDateTime']).strftime('%H:%M')    
    attended            = [ these_clients[x['ClientId']]['LastName'] + ', ' + these_clients[x['ClientId']]['FirstName'] for x in this_attendance['Visits'] if x['SignedIn'] ]
    lateCxl             = [ these_clients[x['ClientId']]['LastName'] + ', ' + these_clients[x['ClientId']]['FirstName'] for x in this_attendance['Visits'] if x['LateCancelled'] ]
    other               = [ these_clients[x['ClientId']]['LastName'] + ', ' + these_clients[x['ClientId']]['FirstName'] for x in this_attendance['Visits'] if not x['SignedIn'] and not x['LateCancelled'] ]

    if( not len( attended) ): continue
    attendance[class_time + ' | ' + this_attendance['Staff']['LastName']]  = { 'attended': attended, 'lateCxl': lateCxl, 'other': other }

#sort classes for output
attendance_str  = ''
class_times     = sorted([ x for x in attendance.keys() ])
for class_time in class_times:
    pdb.set_trace()
    if( len( attendance[class_time]['attended'] ) ):
        attendance_str  = attendance_str + '\n\n' + class_time +'\n\nAttended:\n' + '\n'.join(attendance[class_time]['attended'])
    if( len( attendance[class_time]['lateCxl'] ) ):
        attendance_str  = attendance_str + '\n\nLate Cancel:\n' + '\n'.join(attendance[class_time]['lateCxl'])
    if( len( attendance[class_time]['other'] ) ):
        attendance_str  = attendance_str + '\n\nOther:\n' + '\n'.join(attendance[class_time]['other'])

url = creds['webhook']
sc = SlackClient(creds['OAuth'])
sc.api_call( "chat.postMessage", channel=creds['channel'], text= attendance_str )

url_ext     = "/public/v6/sale/sales?StartSaleDateTime=" + dt.date.today().strftime( '%Y-%m-%d' ) + "T00:00:00.00"
sales       = execRequest( url_ext, headers, conn, type = "GET" )['Sales']

url_ext     = "/public/v6/sale/products"
products    = execRequest( url_ext, headers, conn, type = "GET" )['Products']
products    = { int(x['Id']): x for x in products }

url_ext     = "/public/v6/sale/services"
services    = execRequest( url_ext, headers, conn, type = "GET" )['Services']
services    = { int(x['Id']): x for x in services }

url_ext         = "/public/v6/sale/contracts?locationid=1"
contracts       = execRequest( url_ext, headers, conn, type = "GET" )['Contracts']
contract_items  = {int(y[0]['Id']): y[0] for y in [ x['ContractItems'] for x in contracts ] }
contracts       = { int(x['Id']): x for x in contracts }

products.update( services )
products.update( contracts )
products.update( contract_items )

# sales           = 0
products_sold   = [ ]
for sale in sales:
    # sales += 
    for item in sale['PurchasedItems']:
        item = int(item['Id'])
        if( item in products.keys() ):
            products_sold.append( products[item]['Name'] )
        else:
            products_sold.append( 'Unknown item ' + str( item ) )

products_sold   = dict(Counter( products_sold ))
sales_str       = '\nSales:\n'
for product, qnty in products_sold.items():
    sales_str   = sales_str + product.strip() + ': ' + str( qnty ) + '\n'

sc.api_call( "chat.postMessage", channel=creds['channel'], text= sales_str )    

