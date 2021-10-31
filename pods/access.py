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

def data_details_return(data, data_set):
    """Update the data details component of the data dictionary with details drawn from the data_resources.json file."""
    data.update(data_resources[data_set])
    return data



def download_data(dataset_name=None, prompt=prompt_stdin):
    """Check with the user that the are happy with terms and conditions for the data set, then download it."""

    dr = data_resources[dataset_name]
    if not authorize_download(dataset_name, prompt=prompt):
        raise Exception("Permission to download data set denied.")

    if "suffices" in dr:
        for url, filenames, suffices in zip(dr["urls"], dr["files"], dr["suffices"]):
            for filename, suffix in zip(filenames, suffices):
                download_url(
                    url=os.path.join(url, filename).replace(" ", "%20"),
                    dir_name = DATAPATH,
                    save_name = filename,
                    store_directory=dataset_name,
                    suffix=suffix,
                )
    elif "dirs" in dr:
        for url, dirnames, filenames in zip(dr["urls"], dr["dirs"], dr["files"]):
            for filename, dirname in zip(filenames, dirnames):
                print(filename, dirname)
                download_url(
                    url=os.path.join(url, dirname, filename).replace(" ", "%20"),
                    dir_name=DATAPATH,
                    save_name = filename,
                    store_directory=os.path.join(dataset_name, dirname),
                )
    else:
        for url, filenames in zip(dr["urls"], dr["files"]):
            for filename in filenames:
                download_url(
                    url=os.path.join(url, filename).replace(" ", "%20"),
                    dir_name=DATAPATH,
                    save_name = filename,
                    store_directory=dataset_name,
                )
    return True

def clear_cache(dataset_name=None):
    """Remove a data set from the cache"""
    dr = data_resources[dataset_name]
    if "dirs" in dr:
        for dirnames, filenames in zip(dr["dirs"], dr["files"]):
            for dirname, filename in zip(dirnames, filenames):
                path = os.path.join(DATAPATH, dataset_name, dirname, filename)
                if os.path.exists(path):
                    logging.info("clear_cache: removing " + path)
                    os.unlink(path)
            for dirname in dirnames:
                path = os.path.join(DATAPATH, dataset_name, dirname)
                if os.path.exists(path):
                    logging.info("clear_cache: remove directory " + path)
                    os.rmdir(path)

    else:
        for filenames in dr["files"]:
            for filename in filenames:
                path = os.path.join(DATAPATH, dataset_name, filename)
                if os.path.exists(path):
                    logging.info("clear_cache: remove " + path)
                    os.unlink(path)


def data_available(dataset_name=None):
    """Check if the data set is available on the local machine already."""
    dr = data_resources[dataset_name]
    if "dirs" in dr:
        for dirnames, filenames in zip(dr["dirs"], dr["files"]):
            for dirname, filename in zip(dirnames, filenames):
                if not os.path.exists(os.path.join(DATAPATH, dataset_name, dirname, filename)):
                    return False
    else:
        for filenames in dr["files"]:
            for filename in filenames:
                if not os.path.exists(os.path.join(DATAPATH, dataset_name, filename)):
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

def pmlr_proceedings_list(data_set):
    proceedings_file = open(os.path.join(data_path, data_set, "proceedings.yaml"), "r")
    proceedings = yaml.load(proceedings_file, Loader=yaml.FullLoader)

def kepler_telescope_urls_files(datasets, messages=True):
    """
    Find which resources are missing on the local disk for the requested Kepler datasets.

    :param star_datasets: the star data sets to be checked for.
    :type star_datasets: tuple of lists containg kepler ids and data sets.
    """

    resource = data_resources["kepler_telescope_base"].copy()
    kepler_url = resource["urls"][0]

    resource["urls"] = []
    resource["files"] =  []

    dataset_dir = os.path.join(DATAPATH, "kepler_telescope")
    if not os.path.isdir(dataset_dir):
        os.makedirs(dataset_dir)
    for dataset in datasets:
        for kepler_id in datasets[dataset]: 
            file_name = "kplr" + kepler_id + "-" + dataset + "_llc.fits"
            cur_dataset_file = os.path.join(dataset_dir, file_name)
            if not os.path.exists(cur_dataset_file):
                file_download = [file_name]
                resource["files"].append(file_download)
                resource["urls"].append(
                    kepler_url + "/" + kepler_id[:4] + "/" + kepler_id + "/"
                )
    return resource


def cmu_urls_files(subj_motions, messages=True):
    """
    Find which resources are missing on the local disk for the requested CMU motion capture motions.

    :param subj_motions: the subject motions to be checked for.
    :type subj_motions: tuple of lists containing subject numbers and motion numbers.
    """
    dr = data_resources["cmu_mocap_full"]
    cmu_url = dr["urls"][0]

    subjects_num = subj_motions[0]
    motions_num = subj_motions[1]

    resource = {"urls": [], "files": []}
    # Convert numbers to strings
    subjects = []
    motions = [list() for _ in range(len(subjects_num))]
    for i in range(len(subjects_num)):
        curSubj = str(int(subjects_num[i]))
        if int(subjects_num[i]) < 10:
            curSubj = "0" + curSubj
        subjects.append(curSubj)
        for j in range(len(motions_num[i])):
            curMot = str(int(motions_num[i][j]))
            if int(motions_num[i][j]) < 10:
                curMot = "0" + curMot
            motions[i].append(curMot)

    all_skels = []

    assert len(subjects) == len(motions)

    all_motions = []

    for i in range(len(subjects)):
        skel_dir = os.path.join(DATAPATH, "cmu_mocap")
        cur_skel_file = os.path.join(skel_dir, subjects[i] + ".asf")

        url_required = False
        file_download = []
        if not os.path.exists(cur_skel_file):
            # Current skel file doesn't exist.
            if not os.path.isdir(skel_dir):
                os.makedirs(skel_dir)
            # Add skel file to list.
            url_required = True
            file_download.append(subjects[i] + ".asf")
        for j in range(len(motions[i])):
            file_name = subjects[i] + "_" + motions[i][j] + ".amc"
            cur_motion_file = os.path.join(skel_dir, file_name)
            if not os.path.exists(cur_motion_file):
                url_required = True
                file_download.append(subjects[i] + "_" + motions[i][j] + ".amc")
        if url_required:
            resource["urls"].append(cmu_url + "/" + subjects[i] + "/")
            resource["files"].append(file_download)
    return resource
