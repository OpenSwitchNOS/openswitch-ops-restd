from tornado.log import app_log
from opsvalidator.base import BaseValidator
from opsvalidator import error
from opsvalidator.error import ValidationError
from opsrest.utils.utils import get_column_data_from_row
from opsrest.notifications.constants import (
    SUBSCRIBER_NAME,
    SUBSCRIBER_TABLE_LOWER,
    SUBSCRIBER_TYPE,
    SUBSCRIBER_TYPE_WS
)


class NotificationSubscriberValidator(BaseValidator):
    resource = SUBSCRIBER_TABLE_LOWER

    def _is_websocket_subscriber(self, subscriber_row):
        subscriber_type = get_column_data_from_row(subscriber_row,
                                                   SUBSCRIBER_TYPE)
        return subscriber_type == SUBSCRIBER_TYPE_WS

    def validate_deletion(self, validation_args):
        app_log.debug("Verifying if the subscriber can be deleted..")
        subscriber_row = validation_args.resource_row
        subscriber_name = get_column_data_from_row(subscriber_row,
                                                   SUBSCRIBER_NAME)

        if self._is_websocket_subscriber(subscriber_row):
            details = "Subscriber: %s. " % subscriber_name
            details += "Cannot explicitly delete WebSocket based subscriber"
            raise ValidationError(error.METHOD_PROHIBITED, details)

    def validate_modification(self, validation_args):
        if validation_args.is_new:
            app_log.debug("Verifying if the subscriber can be added..")
            subscriber_row = validation_args.resource_row
            subscriber_name = get_column_data_from_row(subscriber_row,
                                                       SUBSCRIBER_NAME)

            if self._is_websocket_subscriber(subscriber_row):
                details = "Subscriber: %s. " % subscriber_name
                details += "Cannot explicitly add WebSocket based subscriber"
                raise ValidationError(error.METHOD_PROHIBITED, details)
