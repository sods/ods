import unittest
import numpy as np
import pods
import types
import mock
import sys


# pods.datasets.overide_manual_authorize=True

dataset_helpers = [
    "authorize_download",
    "clear_cache",
    "data_available",
    "discrete",
    "df2arff",
    "download_rogers_girolami_data",
    "downloard_url",
    "datenum",
    "date2num",
    "num2date",
    "datetime64_",
    "data_details_return",
    "download_data",
    "download_url",
    "integer",
    "json_object",
    "list",
    "urlopen",
    "prompt_user",
    "cmu_mocap",
    "cmu_urls_files",
    "kepler_telescope_urls_files",
    "kepler_telescope",
    "decimalyear",
    "permute",
    "categorical",
    "quote",
    "timestamp",
    "swiss_roll_generated",
    "to_arff",
    "prompt_stdin",
]


def list_datasets(module):
    """List all available datasets names and calling functions."""
    import types

    l = []
    for a in dir(module):
        func = module.__dict__.get(a)
        if a not in dataset_helpers:
            if isinstance(func, types.FunctionType):
                l.append((a, func))
    return l


positive_return_values = ["Y", "y", "Yes", "YES", "yes", "yEs"]
negative_return_values = ["N", "n", "No", "NO", "no", "nO", "eggs"]

dataset_test = []
for name, func in list_datasets(pods.datasets):
    dataset_test.append(
        {
            "dataset_name": name,
            "dataset_function": func,
            "arg": None,
            "docstr": func.__doc__,
        }
    )

dataset_selection = [
    "robot_wireless",
    "creep_rupture",
    "olympic_marathon_men",
    "xw_pen",
    "ripley_prnn_data",
]


def gtf_(dataset_name, dataset_function, arg=None, docstr=None):
    """Generate test function for testing the given data set."""

    def test_function(self):
        with mock.patch('builtins.input', "Y"):
            if arg is None:
                tester = DatasetTester(dataset_function)
            else:
                tester = DatasetTester(dataset_function, arg)
            tester.checkdims()

    test_function.__name__ = "test_" + dataset_name
    test_function.__doc__ = (
        "datasets_tests: Test function pods.datasets." + dataset_name
    )
    return test_function


def populate_datasets(cls, dataset_test):
    """populate_dataset: Auto create dataset test functions."""
    for dataset in dataset_test:
        base_funcname = "test_" + dataset["dataset_name"]
        funcname = base_funcname
        i = 1
        while funcname in cls.__dict__.keys():
            funcname = base_funcname + str(i)
            i += 1
        _method = gtf_(**dataset)
        setattr(cls, _method.__name__, _method)


class DatasetTester(unittest.TestCase):
    """
    This class is the base class we use for testing a dataset.
    """

    def __init__(self, dataset, name=None, **kwargs):
        if name is None:
            name = dataset.__name__
        self.name = name
        self.dataset = dataset
        self.kwargs = kwargs
        with mock.patch('builtins.input', return_value="Y"):
            self.d = self.dataset(**self.kwargs)
        self.ks = self.d.keys()
        self.checkdims()
        self.checkstats()

    def checkdims(self):
        """Check the dimensions of the data in the dataset"""
        if "Y" in self.ks and "X" in self.ks:
            self.assertTrue(self.d["X"].shape[0] == self.d["Y"].shape[0])
        if "Ytest" in self.ks and "Xtest" in self.ks:
            self.assertTrue(self.d["Xtest"].shape[0] == self.d["Ytest"].shape[0])
        if "Y" in self.ks and "Ytest" in self.ks:
            self.assertTrue(self.d["Y"].shape[1] == self.d["Ytest"].shape[1])
        if "X" in self.ks and "Xtest" in self.ks:
            self.assertTrue(self.d["X"].shape[1] == self.d["Xtest"].shape[1])

        if "covariates" in self.ks and "X" in self.ks:
            self.assertTrue(len(self.d["covariates"]) == self.d["X"].shape[1])

        if "response" in self.ks and "Y" in self.ks:
            self.assertTrue(len(self.d["response"]) == self.d["Y"].shape[1])

    def checkstats(self):
        pass


class DatasetsTests(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(DatasetsTests, self).__init__(*args, **kwargs)
        # Auto create the test functions
        # for dataset in dataset_test:
        #     """Auto create dataset test functions."""
        #     base_funcname = 'test_' + dataset['dataset_name']
        #     funcname = base_funcname
        #     i = 1
        #     while(funcname in self.__dict__.keys()):
        #         funcname = base_funcname +str(i)
        #         i += 1
        #     test_function = gtf_(**dataset)
        #     test_function.__name__ = funcname
        #     self.__dict__[funcname]=types.MethodType(test_function, self)

    def download_data(self, dataset_name):
        """datasets_tests: Test the data download."""
        pods.access.clear_cache(dataset_name)
        self.assertFalse(pods.access.data_available(dataset_name))
        with mock.patch('builtins.input', return_value="Y"):
            pods.access.download_data(dataset_name)
        self.assertTrue(pods.access.data_available(dataset_name))

    def test_input(self):
        """datasets_tests: Test the prompt input checking code"""
        for v in positive_return_values:
            with mock.patch('builtins.input', return_value=v):
                self.assertTrue(pods.access.prompt_stdin("Do you pass?"))

        for v in negative_return_values:
            with mock.patch('builtins.input', return_value=v):
                self.assertFalse(pods.access.prompt_stdin("Do you fail?"))

    def test_authorize_download(self):
        """datasets_tests: Test the download authorization code."""
        with mock.patch('builtins.input', return_value="Y"):
            for dataset_name in dataset_selection:
                self.assertTrue(pods.access.authorize_download(dataset_name))

    def test_clear_cache(self):
        """datasets_tests: Test the clearing of the data cache for a data set"""
        for dataset_name in dataset_selection:
            print("Remove data", dataset_name)
            pods.access.clear_cache(dataset_name)
            self.assertFalse(pods.access.data_available(dataset_name))

    def test_data_downloads(self):
        """datasets_tests: Test the data download."""
        for dataset_name in dataset_selection:
            yield self.download_data, dataset_name


populate_datasets(DatasetsTests, dataset_test)
