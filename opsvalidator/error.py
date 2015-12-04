# validation error codes

VERIFICATION_FAILED = 10001
NO_REFERENCED_BY = 10002
FAILED_REFERENCED_BY = 10003


errors = {
        VERIFICATION_FAILED : 'verification failed',
        NO_REFERENCED_BY : 'missing referenced_by resource',
        FAILED_REFERENCED_BY : 'verification failed for referenced_by resource',
        }

class ValidationException(Exception):
    pass


class ValidationError(ValidationException):
    """
    Validator modules raise ValidationError exception upon failure
    """
    default_error_code = VERIFICATION_FAILED
    default_error_message = errors[default_error_code]
    default_detail = {}

    def __init__(self, code=None, detail=None):
        code = code or self.default_error_code
        message = errors[code]
        detail = detail or self.default_detail

        self.error = {'code': code,
                      'message': message,
                      'detail': detail}
