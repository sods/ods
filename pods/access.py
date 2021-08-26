from __future__ import print_function
from __future__ import absolute_import, division
import sys
import os

import json
import yaml

import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    filename="/tmp/sods.log",
    filemode="w",
)

from .config import *

DATAPATH = os.path.expanduser(os.path.expandvars(config.get("datasets", "dir")))
overide_manual_authorize = False

# Read data resources from json file.
# Don't do this when ReadTheDocs is scanning as it breaks things
on_rtd = os.environ.get("READTHEDOCS", None) == "True"  # Checks if RTD is scanning

if not (on_rtd):
    path = os.path.join(os.path.dirname(__file__), "data_resources.json")
    from io import open as iopen

    json_data = iopen(path, encoding="utf-8").read()
    data_resources = json.loads(json_data)

if not (on_rtd):
    path = os.path.join(os.path.dirname(__file__), "football_teams.json")
    from io import open as iopen

    json_data = iopen(path, encoding="utf-8").read()
    football_dict = json.loads(json_data)


def prompt_stdin(prompt):
    """Ask user for agreeing to data set licenses."""
    # raw_input returns the empty string for "enter"
    yes = set(["yes", "y"])
    no = set(["no", "n"])

    try:
        print(prompt)
        if sys.version_info >= (3, 0):
            choice = input().lower()
        else:
            choice = raw_input().lower()
        # would like to test for which exceptions here
    except:
        print("Stdin is not implemented.")
        print("You need to set")
        print("overide_manual_authorize=True")
        print("to proceed with the download. Please set that variable and continue.")
        raise 

    if choice in yes:
        return True
    elif choice in no:
        return False
    else:
        print("Your response was a " + choice)
        print("Please respond with 'yes', 'y' or 'no', 'n'")

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


def download_data(dataset_name=None, prompt=prompt_stdin):
    """Check with the user that the are happy with terms and conditions for the data set, then download it."""

    dr = data_resources[dataset_name]
    if not authorize_download(dataset_name, prompt=prompt):
        raise Exception("Permission to download data set denied.")

    if "suffices" in dr:
        for url, files, suffices in zip(dr["urls"], dr["files"], dr["suffices"]):
            for file, suffix in zip(files, suffices):
                download_url(
                    url=os.path.join(url, file),
                    dir_name=DATAPATH,
                    store_directory=dataset_name,
                    suffix=suffix,
                )
    elif "dirs" in dr:
        for url, dirs, files in zip(dr["urls"], dr["dirs"], dr["files"]):
            for file, dir in zip(files, dirs):
                print(file, dir)
                download_url(
                    url=os.path.join(url, dir, file),
                    dir_name=DATAPATH,
                    store_directory=os.path.join(dataset_name, dir),
                )
    else:
        for url, files in zip(dr["urls"], dr["files"]):
            for file in files:
                download_url(
                    url=os.path.join(url, file),
                    dir_name=DATAPATH,
                    store_directory=dataset_name,
                )
    return True






def clear_cache(dataset_name=None):
    """Remove a data set from the cache"""
    dr = data_resources[dataset_name]
    if "dirs" in dr:
        for dirs, files in zip(dr["dirs"], dr["files"]):
            for dir, file in zip(dirs, files):
                path = os.path.join(DATAPATH, dataset_name, dir, file)
                if os.path.exists(path):
                    logging.info("clear_cache: removing " + path)
                    os.unlink(path)
            for dir in dirs:
                path = os.path.join(DATAPATH, dataset_name, dir)
                if os.path.exists(path):
                    logging.info("clear_cache: remove directory " + path)
                    os.rmdir(path)

    else:
        for file_list in dr["files"]:
            for file in file_list:
                path = os.path.join(DATAPATH, dataset_name, file)
                if os.path.exists(path):
                    logging.info("clear_cache: remove " + path)
                    os.unlink(path)


def data_available(dataset_name=None):
    """Check if the data set is available on the local machine already."""
    dr = data_resources[dataset_name]
    if "dirs" in dr:
        for dirs, files in zip(dr["dirs"], dr["files"]):
            for dir, file in zip(dirs, files):
                if not os.path.exists(os.path.join(DATAPATH, dataset_name, dir, file)):
                    return False
    else:
        for file_list in dr["files"]:
            for file in file_list:
                if not os.path.exists(os.path.join(DATAPATH, dataset_name, file)):
                    return False
    return True


def authorize_download(dataset_name=None, prompt=prompt_stdin):
    """Check with the user that the are happy with terms and conditions for the data set."""
    print("Acquiring resource: " + dataset_name)
    # TODO, check resource is in dictionary!
    print("")
    dr = data_resources[dataset_name]
    print("Details of data: ")
    print(dr["details"])
    print("")
    if dr["citation"]:
        print("Please cite:")
        print(dr["citation"])
        print("")
    if dr["size"]:
        print(
            "After downloading the data will take up "
            + str(dr["size"])
            + " bytes of space."
        )
        print("")
    print("Data will be stored in " + os.path.join(DATAPATH, dataset_name) + ".")
    print("")
    if overide_manual_authorize:
        if dr["license"]:
            print("You have agreed to the following license:")
            print(dr["license"])
            print("")
        return True
    else:
        if dr["license"]:
            print("You must also agree to the following license:")
            print(dr["license"])
            print("")
        return prompt("Do you wish to proceed with the download? [yes/no]")

