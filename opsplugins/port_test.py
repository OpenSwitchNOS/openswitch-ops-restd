from opsvalidator.base import *
from opsvalidator import error
from opsvalidator.error import ValidationError
from tornado.log import app_log

from opsrest.verify import verify_referenced_by

class PortTestingValidator(BaseValidator):
    resource = "port"

    def validate_create(self, validation_args):
        resource = validation_args.resource
        idl = validation_args.idl
        schema = validation_args.schema
        data = validation_args.data

        # A port can only be created if it is being referenced
        # by another resource. 'data' must have the information
        # of the resource that is going to reference this newly
        # created port.
        if 'referenced_by' not in data:
            error_code = error.NO_REFERENCED_BY
            raise ValidationError(error_code)

        # verify resource defined by 'referenced_by' uri is valid
        try:
            verify_referenced_by(data['referenced_by'], resource, schema, idl)
        except Exception, e:
            # verification of referenced_by failed
            error_code = error.FAILED_REFERENCED_BY
            details = e
            raise ValidationError(error_code, details)

        app_log.debug('Validation Successful')
