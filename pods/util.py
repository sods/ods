from __future__ import print_function
from __future__ import absolute_import, division
import sys
import os

from .config import *


def download_url(
    url, dir_name=".", save_name=None, store_directory=None, messages=True, suffix=""
):
    """Download a file from a url and save it to disk."""
    if sys.version_info >= (3, 0):
        from urllib.parse import quote
        from urllib.request import urlopen
        from urllib.error import HTTPError, URLError
    else:
        from urllib2 import quote
        from urllib2 import urlopen
        from urllib2 import URLError as HTTPError
    i = url.rfind("/")
    file = url[i + 1 :]
    if store_directory is not None:
        dir_name = os.path.join(dir_name, store_directory)
    if save_name is None:
        save_name = file
    save_name = os.path.join(dir_name, save_name)
    print("Downloading ", url, "->", save_name)
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    try:
        response = urlopen(url + suffix)
    except HTTPError as e:
        if not hasattr(e, "code"):
            raise
        if e.code > 399 and e.code < 500:
            raise ValueError(
                "Tried url "
                + url
                + suffix
                + " and received client error "
                + str(e.code)
            )
        elif e.code > 499:
            raise ValueError(
                "Tried url "
                + url
                + suffix
                + " and received server error "
                + str(e.code)
            )
    except URLError as e:
        raise ValueError(
            "Tried url " + url + suffix + " and failed with error " + str(e.reason)
        )
    with open(save_name, "wb") as f:
        meta = response.info()
        content_length_str = meta.get("Content-Length")
        if content_length_str:
            # if sys.version_info>=(3,0):
            try:
                file_size = int(content_length_str)
            except:
                try:
                    file_size = int(content_length_str[0])
                except:
                    file_size = None
            if file_size == 1:
                file_size = None
            # else:
            #    file_size = int(content_length_str)
        else:
            file_size = None

        status = ""
        file_size_dl = 0
        block_sz = 8192
        line_length = 30
        percentage = 1.0 / line_length

        if file_size:
            print(
                "|"
                + "{:^{ll}}".format(
                    "Downloading {:7.3f}MB".format(file_size / (1048576.0)),
                    ll=line_length,
                )
                + "|"
            )
            from itertools import cycle

            cycle_str = cycle(">")
            sys.stdout.write("|")

        while True:
            buff = response.read(block_sz)
            if not buff:
                break
            file_size_dl += len(buff)
            f.write(buff)

            # If content_length_str was incorrect, we can end up with many too many equals signs, catches this edge case
            # correct_meta = float(file_size_dl)/file_size <= 1.0

            if file_size:
                if (float(file_size_dl) / file_size) >= percentage:
                    sys.stdout.write(next(cycle_str))
                    sys.stdout.flush()
                    percentage += 1.0 / line_length
                # percentage = "="*int(line_length*float(file_size_dl)/file_size)
                # status = r"[{perc: <{ll}}] {dl:7.3f}/{full:.3f}MB".format(dl=file_size_dl/(1048576.), full=file_size/(1048576.), ll=line_length, perc=percentage)
            else:
                sys.stdout.write(" " * (len(status)) + "\r")
                status = r"{dl:7.3f}MB".format(
                    dl=file_size_dl / (1048576.0),
                    ll=line_length,
                    perc="."
                    * int(line_length * float(file_size_dl / (10 * 1048576.0))),
                )
                sys.stdout.write(status)
                sys.stdout.flush()

            # sys.stdout.write(status)

        if file_size:
            sys.stdout.write("|")
            sys.stdout.flush()

        print(status)
        # if we wanted to get more sophisticated maybe we should check the response code here again even for successes.
