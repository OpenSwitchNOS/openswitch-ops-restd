# Copyright (C) 2015-2016 Hewlett Packard Enterprise Development LP
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

from opsrest.handlers import login, ovsdbapi, config, customrest
from opsrest.handlers.reststaticfilehandler import RESTStaticFileHandler
from custom.logcontroller import LogController
from custom.accountcontroller import AccountController

REGEX_RESOURCE_ID = '?(?P<resource_id>[A-Za-z0-9-_]+[$]?)?/?'

url_patterns =\
    [(r'/login', login.LoginHandler),
     (r'/rest/v1/system/full-configuration', config.ConfigHandler),
     (r'/rest/v1/system', ovsdbapi.OVSDBAPIHandler),
     (r'/rest/v1/system/.*', ovsdbapi.OVSDBAPIHandler)]

custom_url_patterns =\
    [(r'/rest/v1/logs', customrest.CustomRESTHandler, LogController),
     (r'/account', customrest.CustomRESTHandler, AccountController)]

static_url_patterns =\
    [(r"/api/(.*)", RESTStaticFileHandler,
     {"path": "/srv/www/api", "default_filename": "index.html"}),
     (r"/(.*)", RESTStaticFileHandler,
     {"path": "/srv/www/static", "default_filename": "index.html"})]
