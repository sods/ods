#!/usr/bin/env python

import nose, warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    nose.main("pods", defaultTest="pods/testing", argv=["", "--show-skipped"])
