import tornado.ioloop
from tornado.log import app_log

import ops.dc

from opslib import restparser
from opsrest.settings import settings

import json
from ovs.db.idl import Transaction


"""
An example script showing using tornado's ioloop
to write to OVSDB using ops.dc module.

Tornado framework's IOLoop should be preferred over
'while' for writing scripts that work with OVSDB.

Please refer to http://www.tornadoweb.org/en/stable/ioloop.html
"""
def run(*args, **kwargs):
    idl = args[0]
    txn = args[1]

    # NOTE: Use add_handler to monitor socket so that
    # idl.run() is called only when there is data to be
    # consumed. Look at opsrest.manager to get an idea

    idl.run()
    result = txn.commit()
    error = txn.get_error()

    if result == Transaction.INCOMPLETE:
        tornado.ioloop.IOLoop.current().add_callback(run, idl, txn)
    else:
        # transaction completed
        print result, error
        tornado.ioloop.IOLoop.current().stop()

def write(*args, **kwargs):
    data = args[0]
    extschema = args[1]
    idl = args[2]

    try:
        txn = Transaction(idl)
        (idl, txn) = ops.dc.write(data, extschema, idl, txn)

        result = txn.commit()
        error = txn.get_error()

        if result == Transaction.INCOMPLETE:
            tornado.ioloop.IOLoop.current().add_callback(run, idl, txn)
        else:
            # transaction completed
            print result, error
            tornado.ioloop.IOLoop.current().stop()

    except Exception as e:
        tornado.ioloop.IOLoop.current().stop()

def begin(*args, **kwargs):
    idl = args[2]
    idl.run()
    if idl.change_seqno < 1:
        tornado.ioloop.IOLoop.current().add_callback(begin, *args)
    else:
        tornado.ioloop.IOLoop.current().add_callback(write, *args)

if __name__ == '__main__':

    extschema = restparser.parseSchema(settings['ext_schema'])
    ovsschema = settings['ovs_schema']
    remote = settings['ovs_remote']

    # load the json file containing the data
    filename = 'config.json'
    with open(filename) as data_file:
        _data = json.loads(data_file.read())

    # register with OVSDB, create a transaction object
    idl = ops.dc.register(extschema, ovsschema, remote)

    # ioloop
    ioloop = tornado.ioloop.IOLoop.instance()
    ioloop.add_callback(begin, _data, extschema, idl)
    ioloop.start()
