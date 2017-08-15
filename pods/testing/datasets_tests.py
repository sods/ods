import unittest
import numpy as np
import pods
import mock
import sys

#pods.datasets.overide_manual_authorize=True

if sys.version_info>=(3,0):
    user_input = 'builtins.input'
else:
    user_input = '__builtin__.raw_input'


positive_return_values = ['Y', 'y', 'Yes', 'YES', 'yes', 'yEs']
negative_return_values = ['N', 'n', 'No', 'NO', 'no', 'nO', 'eggs']

dataset_selection = ['robot_wireless',
                     'creep_rupture',
                     'olympic_marathon_men',
                     'xw_pen',
                     'ripley_prnn_data']

dataset_funcs = [pods.datasets.robot_wireless,
                 pods.datasets.google_trends,
                 pods.datasets.xw_pen,
                 pods.datasets.epomeo_gpx]

class DatasetTester(unittest.TestCase):
    """
    This class is the base class we use for testing a dataset.
    """
    def __init__(self, dataset, name=None, **kwargs):
        if name is None:
            name=dataset.__name__
        self.name = name
        self.dataset = dataset
        self.kwargs = kwargs
        self.d = self.dataset(**self.kwargs)
        self.ks = self.d.keys()
        
    def checkdims(self):
        if 'Y' in self.ks and 'X' in self.ks:
            self.assertTrue(self.d['X'].shape[0]==self.d['Y'].shape[0])
        if 'Ytest' in self.ks and 'Xtest' in self.ks:
            self.assertTrue(self.d['Xtest'].shape[0]==self.d['Ytest'].shape[0])
        if 'Y' in self.ks and 'Ytest' in self.ks:
            self.assertTrue(self.d['Y'].shape[1]==self.d['Ytest'].shape[1])
        if 'X' in self.ks and 'Xtest' in self.ks:
            self.assertTrue(self.d['X'].shape[1]==self.d['Xtest'].shape[1])

        if 'covariates' in self.ks and 'X' in self.ks:
            self.assertTrue(len(self.d['covariates'])==self.d['X'].shape[1])

        if 'response' in self.ks and 'Y' in self.ks:
            self.assertTrue(len(self.d['response'])==self.d['Y'].shape[1])


class DatasetsTests(unittest.TestCase):

    def download_data(self, dataset_name):
        """Test the data download."""
        pods.datasets.clear_cache(dataset_name)
        self.assertFalse(pods.datasets.data_available(dataset_name))
        with mock.patch(user_input, return_value='Y'):
            pods.datasets.download_data(dataset_name)
        self.assertTrue(pods.datasets.data_available(dataset_name))

    def data_check(self, f):
        with mock.patch(user_input, 'Y'):
            tester = DatasetTester(f)
        tester.checkdims()

    def test_prompt_stdin(self):
        """Test the prompt input checking code"""
        for v in positive_return_values:
            with mock.patch(user_input, return_value=v):
                self.assertTrue(pods.datasets.prompt_stdin("Do you pass?"))     

        for v in negative_return_values:
            with mock.patch(user_input, return_value=v):
                self.assertFalse(pods.datasets.prompt_stdin("Do you fail?"))

    def test_authorize_download(self):
        """Test the download authorization code."""
        with mock.patch(user_input, return_value='Y'):
            for dataset_name in dataset_selection:
                self.assertTrue(pods.datasets.authorize_download(dataset_name))

    def test_clear_cache(self):
        """Test the clearing of the data cache for a data set"""
        for dataset_name in dataset_selection:
            print("Remove data", dataset_name)
            pods.datasets.clear_cache(dataset_name)
            self.assertFalse(pods.datasets.data_available(dataset_name))

    def test_data_downloads(self):
        """Test the data tdownload."""
        for dataset_name in dataset_selection:
            yield self.download_data, dataset_name

    def test_data(self):
        """Test the data that has been downloaded."""
        for data_f in dataset_funcs:
            yield self.data_check, data_f


    # def test_google_trends(self):
    #     f = pods.datasets.google_trends
    #     with mock.patch(user_input, 'Y'):
    #         tester = DatasetTester(f)
    #     tester.checkdims()

           

        
