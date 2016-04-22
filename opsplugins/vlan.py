from opsvalidator.base import *
from opsvalidator import error
from opsvalidator.error import ValidationError
from opsrest.utils import *
from opsrest.exceptions import MethodNotAllowed
from tornado.log import app_log


class VlanValidator(BaseValidator):
    resource = "vlan"

    def validate_deletion(self, validation_args):
        vlan_row = validation_args.resource_row
        vlan_name = utils.get_column_data_from_row(vlan_row, "name")
        if vlan_name == 'DEFAULT_VLAN_1':
            raise MethodNotAllowed
