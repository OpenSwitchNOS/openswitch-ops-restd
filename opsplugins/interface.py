from opsvalidator.base import *
from opsvalidator import error
from opsvalidator.error import ValidationError
from opsrest.utils import *
from opsrest.exceptions import MethodNotAllowed
from tornado.log import app_log


class InterfaceValidator(BaseValidator):
    resource = "interface"

    def validate_deletion(self, validation_args):
            raise MethodNotAllowed
