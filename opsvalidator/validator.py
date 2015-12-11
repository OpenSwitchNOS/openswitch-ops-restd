import pkgutil
import sys
import imp
from tornado.log import app_log
from opsrest import constants
from opsvalidator.base import BaseValidator, ValidationArgs

g_validators = {}


def init_plugins(plugin_dir):
    find_plugins(plugin_dir)
    register_plugins()


def find_plugins(plugin_dir):
    try:
        file, pathname, description = imp.find_module(plugin_dir)
        app_log.debug("Validators for \"%s\":" % plugin_dir)

        for importer, plugin_name, _ in pkgutil.iter_modules([pathname]):
            full_module_name = '%s.%s' % (plugin_dir, plugin_name)
            full_module_name = plugin_name

            if plugin_name not in sys.modules:
                module = importer.find_module(plugin_name)
                module.load_module(full_module_name)
                app_log.debug(plugin_name + " successfully loaded.")

    except ImportError:
        app_log.info("Package \"%s\" does not exist" % plugin_dir)


def register_plugins():
    app_log.debug("Registering plugins...")

    for plugin in BaseValidator.__subclasses__():
        if plugin.resource is not None and plugin.resource != "":
            if plugin.resource in g_validators:
                app_log.debug("%s exists, appending" % plugin.resource)
                g_validators[plugin.resource].append(plugin())
            else:
                app_log.debug("%s is a new plugin, adding" % plugin.resource)
                g_validators[plugin.resource] = [plugin()]
        else:
            app_log.info("Invalid resource defined for %s" % plugin.type())


def exec_validator(idl, schema, resource, method, data=None):
    app_log.debug("Executing validator...")

    # Validate based on the child resource if it exists, which should
    # be most cases.
    if resource.next is not None:
        resource_name = resource.next.table.lower()
    else:
        resource_name = resource.table.lower()

    if resource_name in g_validators:
        resource_validators = g_validators[resource_name]

        validation_args = ValidationArgs(idl, schema, resource, data)

        for validator in resource_validators:
            app_log.debug("Invoking validator \"%s\" for resource \"%s\"" %
                          (validator.type(), resource_name))

            validate_by_method(validator, method, validation_args)
    else:
        app_log.debug("Custom validator for \"%s\" does not exist" %
                      resource_name)


def validate_by_method(validator, method, validation_args):
    if method == constants.REQUEST_TYPE_CREATE:
        validator.validate_create(validation_args)
    elif method == constants.REQUEST_TYPE_UPDATE:
        validator.validate_update(validation_args)
    elif method == constants.REQUEST_TYPE_DELETE:
        validator.validate_delete(validation_args)
    else:
        app_log.debug("Unsupported validation for method %s" % method)
