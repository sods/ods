import sys
import os

from config import *


def download_url(url, dir_name='.', save_name=None, store_directory=None, messages=True, suffix=''):
    """Download a file from a url and save it to disk."""
    import urllib2
    i = url.rfind('/')
    file = url[i+1:]
    print file
    if store_directory is not None:
        dir_name = os.path.join(dir_name, store_directory)
    if save_name is None:
        save_name = file
    save_name = os.path.join(dir_name, save_name)
    print "Downloading ", url, "->", save_name
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    try:
        response = urllib2.urlopen(url+suffix)
    except urllib2.URLError, e:
        if not hasattr(e, "code"):
            raise
        response = e
        if response.code > 399 and response.code<500:
            raise ValueError('Tried url ' + url + suffix + ' and received client error ' + str(response.code))
        elif response.code > 499:
            raise ValueError('Tried url ' + url + suffix + ' and received server error ' + str(response.code))
    with open(save_name, 'wb') as f:
        meta = response.info()
        content_length_str = meta.getheaders("Content-Length")
        if content_length_str:
            file_size = int(content_length_str[0])
        else:
            file_size = None
        status = ""
        file_size_dl = 0
        block_sz = 8192
        line_length=30
        while True:
            buff = response.read(block_sz)
            if not buff:
                break
            file_size_dl += len(buff)
            f.write(buff)
            sys.stdout.write(" "*(len(status)) + "\r")
            if file_size:
                status = r"[{perc: <{ll}}] {dl:7.3f}/{full:.3f}MB".format(dl=file_size_dl/(1048576.),
                                                                       full=file_size/(1048576.), ll=line_length,
                                                                       perc="="*int(line_length*float(file_size_dl)/file_size))
            else:
                status = r"[{perc: <{ll}}] {dl:7.3f}MB".format(dl=file_size_dl/(1048576.),
                                                                       ll=line_length,
                                                                       perc="."*int(line_length*float(file_size_dl/(10*1048576.))))

            sys.stdout.write(status)
            sys.stdout.flush()
        sys.stdout.write(" "*(len(status)) + "\r")
        print status
        # if we wanted to get more sophisticated maybe we should check the response code here again even for successes.
