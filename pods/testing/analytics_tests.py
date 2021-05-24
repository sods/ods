from nose.tools import eq_, ok_
import unittest
import pods
import pandas as pd
import numpy as np

test_user = "opendsi.sheffield@gmail.com"


def list_analytics_calls(module):
    """List all available datasets names and calling functions."""
    import types

    l = []
    for a in dir(module):
        func = module.__dict__.get(a)
        if a not in dataset_helpers:
            if isinstance(func, types.FunctionType):
                l.append((a, func))
    return l


def gtf_(analytic_name, analytic_function, arg=None, docstr=None):
    """Generate test function for testing the given data set."""

    def test_function(self):
        if arg is None:
            tester = AnalyticTester(analytic_function)
        else:
            tester = AnalyticTester(analytic_function, arg)
        tester.checkdims()

    test_function.__name__ = "test_" + analytic_name
    test_function.__doc__ = "analytics_tests: Test function pods.google." + dataset_name
    return test_function


def populate_analytics(cls, query_filters):
    """populate_analytics: Auto create dataset test functions."""
    for query in query_filters:
        base_funcname = "test_" + query["name"]
        funcname = base_funcname
        i = 1
        while funcname in cls.__dict__.keys():
            funcname = base_funcname + str(i)
            i += 1
        _method = gtf_(**dataset)
        setattr(cls, _method.__name__, _method)


class AnalyticsTester(unittest.TestCase):

    """
    This class is the base class we use for testing a dataset.
    """

    def __init__(self, query, name=None, **kwargs):
        if name is None:
            name = query.__name__
        self.name = name
        self.query = query
        self.kwargs = kwargs
        self.d = self.query(**self.kwargs)


# if pods.google.api_available:
class AnalyticsTests(unittest.TestCase, *args, **kwargs):
    def __init__(self):
        super(AnalyticsTests, self).__init__(*args, **kwargs)
        # for queries in

    @classmethod
    def setup_class(cls):
        cls.analytics = pods.google.analytics()

    @classmethod
    def teardown_class(cls):
        pass

    # Google analytics tests
    def test_other_credentials(self):
        """analytics_tests: Test opening analytics by sharing credentials"""
        d = pods.google.analytics(credentials=self.analytics.credentials)

    def test_existing_service(self):
        """analytics_tests: Test opening analytics with existing service"""
        d = pods.google.analytics(
            service=self.analytics.service, http=self.analytics.http
        )


# populate_analytics(AnalyticsTests, query_filters):
