from nose.tools import eq_, ok_, raises
import pods
import os
import re
import sys

if sys.version_info >= (3, 0):
    from urllib.error import HTTPError, URLError
else:
    from urllib2 import URLError as HTTPError
    from urllib2 import URLError


# details of a test page
test_url = "http://www.bbc.co.uk/"
store_directory = "tmp"
save_name = "bbc_website.html"
title = "<title data-rh=\"true\">BBC - Home</title>"

# details of a non existent page
fake_url = "http://pandemonium.sinclair.spectrum.absolute.blast.google.gobsmackazedare.co.uk/index.html"

bogus_file = "http://www.bbc.co.uk/bogus_file.html"


def test_downloard_url():
    """access_tests: Test downloading of a URL."""

    pods.access.download_url(
        test_url, save_name=save_name, store_directory=store_directory
    )
    filename = os.path.join(store_directory, save_name)

    ok_(os.path.isfile(filename), "File does not exist in suggested location.")
    file = open(filename, "r")

    found_title = False
    for line in file:
        if re.search(title, line):
            found_title = True
    ok_(
        found_title,
        "Could not find " + title + " in " + filename + " downloaded from " + test_url,
    )


@raises(URLError, ValueError)
def test_graceful_failure_fake_url():
    """access_tests: Test graceful failure of a fake url."""
    pods.access.download_url(fake_url)


@raises(HTTPError, ValueError)
def test_graceful_failure_bogus_file():
    """access_tests: Test graceful failure of a bogus file."""
    pods.access.download_url(bogus_file)


import filecmp
import unittest


class AccessTests(unittest.TestCase):
    def test_download_url(self):
        """access_tests: Test the download url"""
        filename = "access.py"
        download_name = "tmp.py"
        # Download the file to current directory
        pods.access.download_url(
            "https://raw.githubusercontent.com/lawrennd/ods/master/pods/" + filename,
            dir_name=".",
            save_name=download_name,
        )
        # Get path of original module
        path = os.path.dirname(pods.__file__)
        # Compare files
        self.assertTrue(filecmp.cmp(os.path.join(path, filename), download_name))
