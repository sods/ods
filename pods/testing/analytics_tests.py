from nose.tools import eq_, ok_
import pods
import pandas as pd
import numpy as np

test_user = 'opendsi.sheffield@gmail.com' 

if pods.google.api_available:
    class Test_analytics:
        def __init__(self):
            pass

        @classmethod
        def setup_class(cls):
            cls.analytics = pods.google.analytics()

        @classmethod
        def teardown_class(cls):
            pass
        
        # Google analytics tests
        def test_other_credentials(self):
            """sheet_tests: Test opening analytics by sharing credentials"""
            d = pods.google.analytics(credentials=self.analytics.credentials)

        def test_existing_service(self):
            """sheet_tests: Test opening analytics with existing service"""
            d = pods.google.analytics(service=self.analytics.service, http=self.analytics.http)




    class Test_analytics():
        """analytics_tests: Class for testing google analytics functionality."""

        @classmethod
        def setup_class(cls):
            pass
