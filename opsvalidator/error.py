VERIFICATION_FAILED = 10001
NO_REFERENCED_BY = 10002
FAILED_REFERENCED_BY = 10003

error_messages = {
    VERIFICATION_FAILED: 'Verification failed',
    NO_REFERENCED_BY: 'Missing referenced_by resource',
    FAILED_REFERENCED_BY: 'Verification failed for referenced_by resource'
}


class ValidatorException(Exception):
    """Base class for Validator exceptions"""
    pass


class ValidatorError(ValidatorException):
    """
    Validator modules raise ValidatorError upon failure
    """
    def __init__(self, code, details=""):
        if code not in error_messages:
            code = VERIFICATION_FAILED

        message = error_messages[code]

        self.error = {'code': code,
                      'message': message,
                      'details': details}
