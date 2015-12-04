from opsvalidator.base import *
from opsvalidator import error
from opsvalidator.error import ValidationError
from tornado.log import app_log

from opsrest.verify import verify_referenced_by

class PortValidator(BaseValidator):
    resource = "port"

    def validate_create(self, validation_args):

        app_log.info('This plugin will verify referenced_by data for Ports')

        resource = validation_args.resource
        idl = validation_args.idl
        schema = validation_args.schema
        data = validation_args.data

        # In REST verification of POST data is done in
        # verify.py but it can be moved to a plugin instead

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
            detail = e
            raise ValidationError(error_code, e)

        app_log.debug('Validation Successful')
        # success if it reaches here
        return True
