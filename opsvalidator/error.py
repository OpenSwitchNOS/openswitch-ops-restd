import json


class APIException(Exception):
    pass


class ValidationError(APIException):
    """
    Validator modules raise ValidationError exception upon failure
    """
    default_error_code = 10001
    default_error_message = 'Validation error'
    default_detail = {}

    def __init__(self, code=None, message=None, detail=None):
        self.code = code
        self.message = message
        self.detail = detail

        if self.code is None:
            self.code = self.default_error_code
        if self.message is None:
            self.message = self.default_error_message
        if self.detail is None:
            self.detail = self.default_detail

    def __str__(self):
        return json.dumps({'code': self.code,
                           'message': self.message,
                           'detail': self.detail})
