import websocket
import ssl
import os
import time

IP = "172.17.0.6"
src_path = os.path.dirname(os.path.realpath(__file__))
src_file = os.path.join(src_path, 'server.crt')

sslopt = {"cert_reqs": ssl.CERT_REQUIRED,
          "check_hostname": False,
          "ca_certs": src_file,
          "ssl_version": ssl.PROTOCOL_SSLv23}

ws = websocket.WebSocket(sslopt=sslopt)
ws.connect("wss://%s/rest/v1/ws/notifications" % IP)
ws.send("Hello, World")
msg = ws.recv()
print(msg)
time.sleep(1000)
