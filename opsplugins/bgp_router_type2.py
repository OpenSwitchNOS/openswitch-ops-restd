from opsvalidator.base import *
from opsvalidator import error
from opsvalidator.error import ValidationError
from tornado.log import app_log

class BgpRouterValidatorType2(BaseValidator):
    resource = "bgp_router"

    def validate_create(self, validation_args):
        app_log.info("validate_create from BgpRouterValidatorType2")

        validation_result = False
        app_log.info("This validation routine will fail")
        if not validation_result:
            code = error.VERIFICATION_FAILED
            details = ['invalid asn', 'invalid type']

            raise ValidationError(code, details)
