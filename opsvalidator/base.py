from tornado.log import app_log
from opsrest import constants


class ValidationArgs(object):
    pass


class BaseValidator(object):
    resource = ""

    def validate(self, validation_args):
        app_log.info("Invoking base validation method")

        if validation_args.method == constants.REQUEST_TYPE_CREATE:
            return self.validate_create(validation_args)
        elif validation_args.method == constants.REQUEST_TYPE_UPDATE:
            return self.validate_update(validation_args)
        elif validation_args.method == constants.REQUEST_TYPE_DELETE:
            return self.validate_delete(validation_args)
        else:
            app_log.info("Unsupported validation for method %s" %
                         validation_args.method)
            return True

    def type(self):
        return self.__class__.__name__

    def validate_create(self, validation_args):
        app_log.info("validate_create not implemented for " + self.type())
        return True

    def validate_update(self, validation_args):
        app_log.info("validate_update not implemented for " + self.type())
        return True

    def validate_delete(self, validation_args):
        app_log.info("validate_delete not implemented for " + self.type())
        return True
