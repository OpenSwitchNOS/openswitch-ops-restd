from halonrest.handlers import base

url_patterns = [
        (r'/login', base.LoginHandler),
        (r'/rest/v1/system/full-configuration', config.ConfigHandler),
        (r'/.*', base.AutoHandler),
]
