from opsvalidator.base import *
from tornado.log import app_log

class BgpRouterValidator(BaseValidator):
    resource = "bgp_router"

    def validate_create(self, validation_args):
        app_log.info("validate_create from BgpRouterValidator")
        return True
