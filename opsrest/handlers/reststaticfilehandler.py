# Copyright (C) 2016 Hewlett Packard Enterprise Development LP
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

import re
from tornado.web import StaticFileHandler
from tornado.log import app_log


class RESTStaticFileHandler(StaticFileHandler):

    def prepare(self):
        if self.request.protocol == "http":
            self.redirect(re.sub(r'^([^:]+)', 'https',
                                 self.request.full_url()), True)
