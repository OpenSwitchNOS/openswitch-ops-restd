from retrying import retry

SW_IP = '10.10.1.1'
HS_IP = '10.10.1.5'
MASK = '24'

PROTOCOL = 'https'
PORT = '443'

# Open SSL Variables
CRT_DIRECTORY_SW = "/etc/ssl/certs/server.crt"
CRT_DIRECTORY_HS = "/usr/local/share/ca-certificates/server.crt"

# SCP Remote part variables
REMOTE_USER = 'root'
REMOTE_SIDE = "destination"
REMOTE_PASS = "procurve"

# Request variables

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_DELETED = 204
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_METHOD_NOT_ALLOWED = 405

# REST AUTHENTICATION
USER = 'netop'
PASSWORD = 'netop'

KEY_SIZE = '1024'
LOGIN_TIMES = 500


def login_to_physical_switch(hs1, step):
    step("\n########## Logging into switch ##########\n")

    login_result = hs1.libs.openswitch_rest.login_post(
        USER, PASSWORD, CRT_DIRECTORY_HS, 2)

    assert login_result.get('status_code') == HTTP_OK, \
        'ERROR: Status code of login is not {}'.format(HTTP_OK)

    return login_result


def set_rest_server(hs1, step):
    step("Set the rest server with {} DUT IP, using {} protocol\
         and {} port".format(SW_IP, PROTOCOL, PORT))
    hs1.libs.openswitch_rest.set_server(SW_IP, PROTOCOL, PORT)

    # Unset the https_proxy for execute REST request
    # there is any library for unset proxy, as it is a
    # short command the library will not be done
    hs1("echo  ; unset https_proxy")


def add_ip_devices(sw1, hs1, step):
    step("Add ip address {} to the host, and add the ip \
         address {} to the switch with the mask as \
         {}".format(HS_IP, SW_IP, MASK))

    # Configure IP and bring UP host 1 interfaces
    hs1.libs.ip.interface('1', addr='{}/{}'.format(HS_IP, MASK), up=True)

    # Configure IP and bring UP switch 1 interfaces
    with sw1.libs.vtysh.ConfigInterfaceMgmt() as ctx:
        ctx.ip_static('{}/{}'.format(SW_IP, MASK))


@retry(stop_max_attempt_number=5, wait_fixed=1000)
def ensure_connectivity(hs1, step):
    step("Ensure connectivity from HOST to DUT")

    # Ping to ensure connectivity
    ping = hs1.libs.ping.ping(5, SW_IP)
    assert ping['transmitted'] == ping['received'], \
        'ERROR: Ping is not transmitted {} and \
        received {}'.format(ping['transmitted'],
                            ping['received'])
