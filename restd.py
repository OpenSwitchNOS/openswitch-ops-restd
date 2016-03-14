#!/usr/bin/env python
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.autoreload
from tornado.options import options
import tornado.web

from opsrest.settings import settings
from opsrest.application import OvsdbApiApplication

from tornado.log import app_log
import subprocess
import os

# enable logging
from tornado.log import enable_pretty_logging
options.logging = settings['logging']
enable_pretty_logging()

SSL_PRIV_DIR = "/etc/ssl/private"
SSL_PASS_KEY_FILE = "/etc/ssl/private/server.pass.key"
SSL_PRIV_KEY_FILE = "/etc/ssl/private/server-private.key"
SSL_CSR_FILE = "/etc/ssl/private/server.csr"
SSL_CRT_FILE = "/etc/ssl/certs/server.crt"


def create_ssl_pki():
    if not os.path.exists(SSL_PRIV_DIR):
        os.mkdir(SSL_PRIV_DIR, 0700)
    passphrase = "pass:"+os.urandom(16)
    subprocess.call(['openssl', 'genrsa', '-des3', '-passout',
                     passphrase, '-out', SSL_PASS_KEY_FILE,
                     '2048'])

    subprocess.call(['openssl', 'rsa', '-passin', passphrase,
                     '-in', SSL_PASS_KEY_FILE,
                     '-out', SSL_PRIV_KEY_FILE])

    subprocess.call(['openssl', 'req', '-new', '-key',
                     SSL_PRIV_KEY_FILE, '-out',
                     SSL_CSR_FILE, '-subj',
                     '/C=US/ST=California/L=Palo Alto/O=HPE'])

    subprocess.call(['openssl', 'x509', '-req', '-days', '365', '-in',
                     SSL_CSR_FILE, '-signkey',
                     SSL_PRIV_KEY_FILE, '-out',
                     SSL_CRT_FILE])
    os.remove(SSL_PASS_KEY_FILE)


def main():
    options.parse_command_line()

    app_log.debug("Creating OVSDB API Application!")
    app = OvsdbApiApplication(settings)

    create_ssl_pki()

    HTTPS_server = tornado.httpserver.HTTPServer(app, ssl_options={
        "certfile": SSL_CRT_FILE,
        "keyfile": SSL_PRIV_KEY_FILE})

    HTTP_server = tornado.httpserver.HTTPServer(app)

    app_log.debug("Server listening to port: %s" % options.HTTPS_port)
    HTTPS_server.listen(options.HTTPS_port)

    app_log.debug("Server listening to port: %s" % options.HTTP_port)
    HTTP_server.listen(options.HTTP_port)

    app_log.info("Starting server!")
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()
