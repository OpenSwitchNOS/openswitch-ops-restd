errors = {

        10001 : 'Validation error',
        10002 : 'Resource already exists in DB.',
        10003 : 'Resource does not exist in DB',
        10004 : 'Table does not exist in DB.',
        10005 : 'POST not allowed.',
        10006 : 'PUT not allowed.',

        }

class ValidationException(Exception):
    pass


class ValidationError(ValidationException):
    """
    Validator modules raise ValidationError exception upon failure
    """
    default_error_code = 10001
    default_error_message = errors[default_error_code]
    default_detail = {}

    def __init__(self, code=None, detail=None):
        code = code or self.default_error_code
        message = errors[code]
        detail = detail or self.default_detail

        self.error = {'code': code,
                      'message': message,
                      'detail': detail}
