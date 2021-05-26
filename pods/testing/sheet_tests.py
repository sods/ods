from nose.tools import eq_, ok_
import pods
import pandas as pd
import numpy as np

test_user = "opendsi.sheffield@gmail.com"

if pods.google.gspread_available and pods.google.api_available:

    class Test_drive:
        def __init__(self):
            pass

        @classmethod
        def setup_class(cls):
            cls.drive = pods.google.drive()
            cls.resource_one = pods.google.resource(
                name="Test file", mime_type=pods.google.sheet_mime
            )
            cls.resource_two = pods.google.resource(
                name="Test file 2", mime_type=pods.google.sheet_mime
            )
            cls.sheet = pods.google.sheet()

        @classmethod
        def teardown_class(cls):
            cls.resource_one.delete(empty_bin=True)
            cls.resource_two.delete(empty_bin=True)
            cls.sheet.resource.delete(empty_bin=True)

        # Google drive tests
        def test_other_credentials(self):
            """sheet_tests: Test opening drive by sharing credentials"""
            d = pods.google.drive(credentials=self.drive.credentials)

        def test_existing_service(self):
            """sheet_tests: Test opening drive with existing service"""
            d = pods.google.drive(service=self.drive.service, http=self.drive.http)

        def resource_listed(self, resource):
            resources = self.drive.ls()
            found_resource = False
            for r in resources:
                if resource._id == r._id:
                    found_resource = True
            ok_(found_resource, msg="Resource not found in listing")

        def resource_not_listed(self, resource):
            resources = self.drive.ls()
            found_resource = False
            for r in resources:
                if resource._id == r._id:
                    found_resource = True
            ok_(not found_resource, msg="Resource found in listing")

        def share_listed(self, resource, user, status):
            shares = resource.share_list()
            found_share = False
            for s in shares:
                if s[0] == user:
                    eq_(s[1], status, msg="User share status incorrect")
                    found_share = True
            ok_(found_share, msg="Share not found in listing")

        def share_not_listed(self, resource, user):
            shares = resource.share_list()
            found_share = False
            for s in shares:
                if s[0] == user:
                    found_share = True
            ok_(not found_share, msg="Share found in listing")

        def test_ls(self):
            """sheet_tests: Test that ls is working."""
            self.resource_listed(self.resource_one)
            self.resource_listed(self.resource_two)
            self.resource_listed(self.sheet.resource)

        def test_create_sheet(self):
            """sheet_tests: Test code's ability to create sheets from existing resource."""
            s = pods.google.sheet(resource=self.resource_one)

        def test_delete(self):
            """sheet_tests: Test that a file can be deleted and undeleted (using trash)"""
            self.resource_one.delete()
            self.resource_not_listed(self.resource_one)
            self.resource_one.undelete()
            self.resource_listed(self.resource_one)

        def test_share(self):
            """sheet_tests: Test that resource can be shared."""
            self.resource_one.share(test_user)
            self.share_listed(self.resource_one, test_user, "writer")
            self.resource_one.share_delete(test_user)
            self.share_not_listed(self.resource_one, test_user)

        def test_share_modify(self):
            """sheet_tests: Test that sharing status can be changed."""
            self.resource_two.share(test_user)
            self.share_listed(self.resource_two, test_user, "writer")
            self.resource_two.share_modify(test_user, "reader")
            self.share_listed(self.resource_two, test_user, "reader")

        def test_name_change(self):
            """sheet_tests: Test that the name of the file on google drive can be changed."""
            new_name = "Testing Name 2"
            self.resource_one.update_name(new_name)
            eq_(
                new_name,
                self.resource_one.get_name(),
                msg="Name change has failed to take effect",
            )

        def test_mime_type(self):
            """sheet_tests: Test that mime_type of file is correct."""
            eq_(
                self.sheet.resource.get_mime_type(),
                pods.google.sheet_mime,
                msg="Mime type of google spread sheet does not match expectation.",
            )

    class Test_sheet:
        """sheet_tests: Class for testing google spreadsheet functionality."""

        @classmethod
        def setup_class(cls):
            cls.col_indent = 3
            cls.header = 4
            pods.datasets.override_manual_authorize = True
            cls.sheet_one = pods.google.sheet()
            cls.resource = pods.google.resource(
                drive=cls.sheet_one.resource.drive, mime_type=pods.google.sheet_mime
            )
            cls.sheet_two = pods.google.sheet(resource=cls.resource)
            cls.data = pods.datasets.movie_body_count()

            cls.sheet_two.write(cls.data["Y"])
            cls.sheet_two.resource.share(
                ["lawrennd@gmail.com", "N.Lawrence@sheffield.ac.uk"]
            )

            cls.sheet_three = pods.google.sheet(
                col_indent=cls.col_indent, header=cls.header
            )
            cls.sheet_three.write(cls.data["Y"])

            cls.data_two = pd.DataFrame(
                [
                    [0.2, "cat", 12],
                    ["orange", "barley", np.nan],
                    [12, 11, 2.3],
                    [2.3, "egg", "plant"],
                    ["Sheffield", "United", "FC"],
                    ["Sheffield", "Wednesday", "FC"],
                ],
                columns=["dog", "flea", "cat"],
                index=["a", "b", "c", "d", "e", "f"],
            )
            cls.update_sheet = pods.google.sheet(
                col_indent=cls.col_indent, header=cls.header
            )
            cls.update_sheet.write(cls.data_two)

            cls.update_sheet_two = pods.google.sheet()
            cls.update_sheet_two.write(cls.data_two)

            cls.update_sheet_three = pods.google.sheet()
            cls.update_sheet_three.write(cls.data_two)

            cls.update_sheet_four = pods.google.sheet()
            cls.update_sheet_four.write(cls.data_two)

        @classmethod
        def teardown_class(cls):
            """sheet_tests: Delete of the sheets created for the tests."""
            cls.sheet_one.resource.delete(empty_bin=True)
            cls.sheet_two.resource.delete(empty_bin=True)
            cls.sheet_three.resource.delete(empty_bin=True)
            cls.update_sheet.resource.delete(empty_bin=True)
            cls.update_sheet_two.resource.delete(empty_bin=True)
            cls.update_sheet_three.resource.delete(empty_bin=True)
            cls.update_sheet_four.resource.delete(empty_bin=True)

        def read_sheet(self, sheet, df):
            """sheet_tests: Test reading."""
            df2 = sheet.read()
            eq_(df2.shape[0], df.shape[0], "Rows of read data frame do not match.")
            eq_(df2.shape[1], df.shape[1], "Columns of read data frame do not match.")
            for column in df.columns:
                if column not in df2.columns:
                    ok_(
                        False, "Missing column " + str(column) + " in downloaded frame."
                    )
            for index in df.index:
                if index not in df2.index:
                    ok_(False, "Missing index " + str(index) + " in downloaded frame.")

        def test_read(self):
            """sheet_tests: Test reading started at origin."""
            print("Test reading of sheet started at origin.")
            self.read_sheet(self.sheet_two, self.data["Y"])

        def test_read_indented(self):
            """sheet_tests: Test reading of indented and headered sheet."""
            print("Test reading of sheet offset from origin.")
            self.read_sheet(self.sheet_three, self.data["Y"])

        def test_drop(self):
            """sheet_tests: Test dropping of rows from sheet."""
            print("Test dropping of rows from sheet.")
            data_three = self.data_two.drop(["c", "e"])
            self.update_sheet.update(data_three)
            self.read_sheet(self.update_sheet, data_three)

        def test_drop_swap(self):
            """sheet_tests: Test dropping and replacing with other rows."""
            print("Test dropping and replacing with other rows.")
            data_three = self.data_two.drop(["c", "e"])
            data_three.loc["barry"] = ["bat", "ball", np.nan]
            data_three.loc["sid"] = ["bart", "simpson", "naff"]
            self.update_sheet_two.update(data_three)
            self.read_sheet(self.update_sheet_two, data_three)

        def test_add(self):
            """sheet_tests: Test adding of rows to sheet."""
            print("Test adding of rows to sheet.")
            data_three = self.data_two.copy()
            data_three.loc["barry"] = ["bat", "ball", np.nan]
            data_three.loc["sid"] = ["bart", "simpson", "naff"]
            self.update_sheet_three.update(data_three)
            self.read_sheet(self.update_sheet_three, data_three)

        def test_update(self):
            """sheet_tests: Test updating of elements in sheet."""
            print("Test updating of elements in sheet.")
            data_three = self.data_two.copy()
            data_three["flea"]["f"] = "United"
            data_three["dog"]["e"] = 23.2
            self.update_sheet_four.update(data_three)
            self.read_sheet(self.update_sheet_four, data_three)
