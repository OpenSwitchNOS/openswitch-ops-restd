import yaml

from tornado.log import app_log

from opsrest.settings import settings
from opsrest.constants import (PASSWD_SRV_SOCK_TYPE_KEY,
                               PASSWD_SRV_PUB_TYPE_KEY)


class PasswordServerConfig(object):
    __instance = None

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(PasswordServerConfig, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        self.passwd_srv_sock_fd = ''
        self.passwd_srv_pub_key_loc = ''
        self.__get_passwd_srv_files_location__()

    def __get_passwd_srv_files_location__(self):
        try:
            passwd_srv_yaml = \
                open(settings['passwd_srv_yaml'], "r")
            passwd_srv_files = yaml.load_all(passwd_srv_yaml)
            for file in passwd_srv_files:
                for k, v in file.items():
                    passwd_srv_list = v
            for element in passwd_srv_list:
                if element['type'] == PASSWD_SRV_SOCK_TYPE_KEY:
                    self.passwd_srv_sock_fd = element['path']
                if element['type'] == PASSWD_SRV_PUB_TYPE_KEY:
                    self.passwd_srv_pub_key_loc = element['path']
            passwd_srv_yaml.close()
        except IOError as e:
            app_log.debug("Failed to open Password Server YAML file: %s" % e)
