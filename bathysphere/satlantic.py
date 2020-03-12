from datetime import datetime, date
from collections import deque
from multiprocessing import Pool
from requests import get
from itertools import repeat
from enum import Enum
from typing import Coroutine, Any
from asyncio import new_event_loop, set_event_loop, BaseEventLoop

try:
    from pandas import read_html
except ImportError as _:
    read_html = None

from bathysphere.datatypes import FileType, File
from bathysphere.utils import synchronous



def indexFileMetadata(url, year, auth=None):
    # type: (str, int, (str,)) -> deque
    """
    Callable method to map a remote HTTP-accessible file catalog by date, and then build an time-indexed structure
    that contains a <coroutine> in the place of file meta_data. This only takes a few seconds, compared to minutes
    for resolving all files. Usually, only some data is needed immediately, so tasks can be resolved on demand and
    cached at a leisurely interactive pace.
    """
    collector = deque()
    for record in resolveTaskTree(indexTaskTree(url=url, enum=year, auth=auth, depth=2)):
        path = "{}/{:04}/{:02}/{:02}/".format(url, *record)
        collector.append(
            {
                "date": date(*record),
                "name": "{}-{:02}-{}".format(*record),
                "url": path,
                "files": _file_metadata_promise(path, auth=auth),
            }
        )
    return collector


def resolveTaskTree(t) -> tuple:
    """
    Recursively run and REDUCE an asynchronous task tree which returns an (index, <coroutine>) tuple. The process
    stops when the final inner method is evaluated.

    This is used internally by `metadata()`. The depth of the task structure is set before runtime, for example,
    see `_map_by_date`.
    """

    i, inner = synchronous(t)
    if inner is None:
        return i,
    yields = ()
    while len(inner):
        yields += tuple([i, *((j,) if type(j) == int else tuple(j))] for j in resolveTaskTree(inner.pop()))
    return yields


def _parse_str_to_float(string):
    # type: (str) -> float
    try:
        if "K" in string:
            return float(string.replace("K", ""))
        else:
            return float(string) / 1000
    except TypeError:
        return -1


def _file_metadata(url, filename, ts, size):
    # type: (str, str, str, str) -> File
    fields = filename.split(".")

    encoding = None
    if len(fields) > 1:
        fmt = fields.pop()
        if "sensors" == fmt:
            encoding = FileType.Config
        elif "xml" == fmt:
            encoding = FileType.Schema
        elif "raw" == fmt:
            encoding = FileType.Raw
        elif "txt" == fmt:
            if fields[-1] == "raw":
                fields.pop()  # convention is to have ".raw.txt"
            encoding = FileType.Log

    time = None
    if len(fields) > 1:  # dated files
        ft = fields.pop()
        try:
            dt_fmt = "%Y%m%d-%H%M%S" if (ft and len(ft) > 13) else "%Y%m%d-%H%M"
            time = datetime.strptime(ft, dt_fmt)
        except ValueError:
            pass

    try:
        sn = int(fields.pop())
    except ValueError:
        sn = None

    path = url + filename

    return File(
        name=filename,
        sn=sn,  # maybe None
        url=path,  # retrieval path
        time=time,  # file time from name, maybe None
        ts=datetime.strptime(ts, "%d-%b-%Y %H:%M"),  # timestamp from server
        kb=_parse_str_to_float(size),  # float kilobytes
        encoding=encoding,
    )


async def _file_metadata_promise(url, auth):
    # type: (str, str) -> tuple
    """
    Produce a coroutine that will yield file metadata for all files in a remote directory/catalog.
    """
    response = get(url, auth=auth)
    if not response.ok:
        return response.content

    df = read_html(response.content, skiprows=3)[0]
    return tuple(
        _file_metadata(url, *r)
        for r in zip(*(df[ii][:-1].tolist() for ii in (1, 2, 3)))
    )


async def indexTaskTree(url, enum, count=0, depth=2, auth=None):
    # type: (str, int, int, int, (str, )) -> datetime or None
    """
    Private method is used by `metadata()` to build a temporal index with multiple levels of resolution on demand.

    Recursively `GET` file metadata in a destination file catalog, based on date, then bathysphere_functions_parse the tabular HTML
    into nested tuples of (index, <coroutine>). The coroutine is then resolved to another (index, <coroutine>) tuple,
    using the `render()` method, until the specified depth is reached.
    """
    def __parse(value):
        return value if type(value) == int else int(value[:-1])

    if count == depth:
        return enum, None

    try:
        formatter = "{{}}/{{:0{}d}}".format(4 if count == 0 else 2)
        insert = __parse(enum)
    except TypeError:
        return enum, None

    sublevel = formatter.format(url, insert)
    response = get(sublevel, auth=auth)
    if not response.ok:
        return enum, None

    collector = deque()
    for record in deque(response.content.decode().split("\n")[3:-1]):
        collector.append(
            indexTaskTree(
                url=sublevel,
                enum=__parse(record),  # name
                count=count + 1,
                depth=depth,
                auth=auth,
            )
        )

    return enum, collector


def _match(x, fmt=None, identity=None):
    # type: (File, set, set) -> bool
    return (not identity or x.sn in identity) and (not fmt or x.encoding in fmt)


def _search(
    queue: deque, pool: Pool, fmt: set = None, identity: set = None, ts: datetime = None
) -> list or None:
    """
    Get all XML and configuration files within a directory

    Find configurations from metadata by serial number and date.

    The files can be:
    - On a remote server
    - In the bathysphere_functions_cache
    - Supplied as a list of dictionaries
    """
    iterators = []
    if identity:
        iterators.append(repeat(identity))
    if fmt:
        iterators.append(repeat(fmt))
    if ts:
        iterators.append(repeat(ts))

    def _chrono(x: File, ts: datetime = None):
        return (
            (x.time is None if ts else x.time is not None),
            (ts - x.time if ts else x.time),
        )

    queue = sorted(queue, key=_chrono, reverse=(False if ts else True))
    if fmt or identity:
        matching = pool.starmap(_match, zip(queue, *iterators))
        queue = deque(queue)
    else:
        return {}, queue

    collector = dict()
    for condition in matching:
        if not condition:
            queue.rotate(1)
            continue
        file = queue.popleft()
        if not collector.get(file.sn, None):
            collector[file.sn] = deque()
        if (
            not ts or len(collector[file.sn]) == 0
        ):  # limit to length 1 for getting most recent
            collector[file.sn].append(file)
            continue

        queue.append(file)  # put the file back if unused

    return collector, queue


def get_files(queue: deque, pool: Pool, **kwargs):
    """
    Create and process a day of raw files
    """
    extracted, queue = _search(
        queue=queue, pool=pool, **kwargs
    )  # get active configuration files
    headers = dict()
    for sn, files in extracted.keys():
        headers[sn] = deque()
        for file in files:
            synchronous(file.get_and_decode())
            if file.encoding == FileType.Config:
                headers[sn].append(file.frames)

    return extracted, headers, queue
