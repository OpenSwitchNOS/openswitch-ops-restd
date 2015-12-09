import httplib

class APIException(Exception):
    status_code = httplib.INTERNAL_SERVER_ERROR
    status = httplib.responses[status_code]

    def __init__(self, detail=None):
        self.detail = detail

class ValidationError(APIException):
    status_code = httplib.BAD_REQUEST
    status = httplib.responses[status_code]

def ParseError(APIException):
    status_code = httplib.BAD_REQUEST
    status = httplib.responses[status_code]

def AuthenticationFailed(APIException):
    status_code = httplib.UNAUTHORIZED
    status = httplib.responses[status_code]

def NotAuthenticated(APIException):
    status_code = httplib.UNAUTHORIZED
    status = httplib.responses[status_code]

def NotFound(APIException):
    status_code = httplib.NOT_FOUND
    status = httplib.responses[status_code]

def MethodNotAllowed(APIException):
    status_code = httplib.METHOD_NOT_ALLOWED
    status = httplib.responses[status_code]
