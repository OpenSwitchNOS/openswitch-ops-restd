class Resource(object):

    """
    Resource class identifies the object in the DB
    on which validation routines can be run.

    This can either be the 'table' to which a new resource
    is being added (POST) or an 'entry' in the table which is being
    modified (PUT/PATCH/DELETE).
    """

    def __init__(self, table, index=None, uuid=None):
        self.table = table
        self.index = index
        self.uuid = uuid

        # optional data
        self.request_uri = None
        self.parsed_uri = None
