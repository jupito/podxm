"""JSON data files."""

import datetime
import json
import logging

import dateutil.parser

log = logging.getLogger(__name__)


def write_json(fp, obj):
    """Write JSON file."""
    json.dump(obj, fp, cls=MyJSONEncoder, ensure_ascii=False, indent=2,
              sort_keys=True)


def read_json(fp):
    """Read JSON file."""
    try:
        return json.load(fp, cls=MyJSONDecoder)
    except json.decoder.JSONDecodeError as e:
        log.error('Error decoding JSON: %s', fp)
        raise


class MyJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder."""
    def __init__(self, *args, **kwargs):
        kwargs.update(default=self.default_decode)
        super().__init__(*args, **kwargs)

    def default_decode(self, o):
        """Return a serializable object for custom objects."""
        if isinstance(o, set):
            return list(o)
        if hasattr(o, '_asdict'):
            d = o._asdict()
            # d['__type__'] = type(o).__name__
            return d
        if hasattr(o, 'as_json'):
            return o.as_json()
        # if isinstance(o, datetime.datetime):
        #     # return {type(o).__name__: o.isoformat()}
        #     return dict(__type__='datetime', year=o.year, month=o.month,
        #                 day=o.day, hour=o.hour, minute=o.minute,
        #                 second=o.second, microsecond=o.microsecond)
        # if isinstance(o, datetime.timedelta):
        #     return dict(__type__='timedelta', days=o.days, seconds=o.seconds,
        #                 microseconds=o.microseconds)

        # if isinstance(o, datetime.datetime):
        #     return {'datetime': o.isoformat()}
        try:
            it = iter(o)
        except TypeError:
            log.error('Cannot JSONify type %s: %s', type(o), o)
        else:
            return list(it)
        # Let the base class default method raise the TypeError.
        return super().default(o)


class MyJSONDecoder(json.JSONDecoder):
    """Custom JSON decoder."""
    def __init__(self, *args, **kwargs):
        kwargs.update(object_hook=self.dict_to_object)
        super().__init__(*args, **kwargs)

    @staticmethod
    def dict_to_object(d):
        """Create custom object from dictionary."""
        if '__type__' in d:
            typ = d.pop('__type__')
            if typ == 'datetime':
                return datetime.datetime(**d)
            elif typ == 'timedelta':
                return datetime.timedelta(**d)
            else:
                d['__type__'] = typ  # Put it back together.
        if len(d) == 1 and 'datetime' in d:
            return dateutil.parser.parse(d['datetime'])
        return d


# def read_json_DEBUG(path):
#     """Read JSON file, with some debug output."""
#     def object_hook(obj):
#         """Called with all decoded objects."""
#         log.debug(obj)
#         return obj
#
#     def object_pairs_hook(lst):
#         """Called with decoded ordered lists of pairs."""
#         for k, v in lst:
#             log.debug(k, v)
#         return lst
#     with open(path, 'r') as fp:
#         return json.load(fp, object_hook=object_hook,
#                          object_pairs_hook=object_pairs_hook,
#                          cls=MyJSONDecoder)
