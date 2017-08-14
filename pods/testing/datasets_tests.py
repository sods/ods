import unittest
import numpy as np
import pods
pods.datasets.overide_manual_authorize=True


class DatasetTester():
    """
    This class is the base class we use for testing a dataset.
    """
    def __init__(self, dataset, name=None, **kwargs):
        if name is None:
            name=dataset.__name__
        self.name = name
        self.dataset = dataset
        self.kwargs = kwargs
        
    def download(self):
        d = self.dataset(kwargs)
        return True

class DatasetsTests(unittest.TestCase):

    def test_robot_wireless(self):
        dataset = pods.datasets.robot_wirless()
        self.assertTrue(DatasetTester(dataset).download())
