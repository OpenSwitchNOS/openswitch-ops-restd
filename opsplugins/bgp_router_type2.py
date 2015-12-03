from opsvalidator.base import *
from opsvalidator.error import ValidationError
from tornado.log import app_log

class BgpRouterValidatorType2(BaseValidator):
    resource = "bgp_router"

    def validate_create(self, validation_args):
        app_log.info("validate_create from BgpRouterValidatorType2")

        validation_result = False
        app_log.info("This validation routine will fail")
        if not validation_result:
            code = 10001
            message = 'BGP Router validation failed'
            detail = ['invalid asn', 'invalid type']

            raise ValidationError(code, message, detail)
        else:
            return True
