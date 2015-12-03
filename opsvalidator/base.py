from tornado.log import app_log


class ValidationArgs(object):
    """
    Arguments from the validation framework used by validators
    """
    def __init__(self, idl, schema, resource, data):
        self.idl = idl
        self.schema = schema
        self.resource = resource
        self.data = data


class BaseValidator(object):
    """
    Base class for validators to provide as a hook and registration
    mechanism. Derived classes will be registered as validators.

    resource: Used for registering a validator with a resource/table name.
              It is used for validator lookup. Derived classes must define
              a value for proper registration/lookup.
    """
    resource = ""

    def type(self):
        return self.__class__.__name__

    def validate_create(self, validation_args):
        app_log.debug("validate_create not implemented for " + self.type())
        return True

    def validate_update(self, validation_args):
        app_log.debug("validate_update not implemented for " + self.type())
        return True

    def validate_delete(self, validation_args):
        app_log.debug("validate_delete not implemented for " + self.type())
        return True
