from nose.tools import eq_, ok_
import pods

test_user = 'opendsi.sheffield@gmail.com' 

if pods.google.gspread_available:
    class Test_google:
        def __init__(self):
            pass

        @classmethod
        def setup_class(cls):
            cls.drive = pods.google.drive()
            cls.resource_one = pods.google.resource(name='Test file', mime_type=pods.google.sheet_mime)
            cls.resource_two = pods.google.resource(name='Test file 2', mime_type=pods.google.sheet_mime)
            cls.sheet = pods.google.sheet()

        @classmethod
        def teardown_class(cls):
            cls.resource_one.delete(empty_bin=True)
            cls.resource_two.delete(empty_bin=True)
            cls.sheet.resource.delete(empty_bin=True)

        # Google drive tests
        def test_other_credentials(self):
            # Test opening drive by sharing credentials
            d = pods.google.drive(credentials=self.drive.credentials)

        def test_existing_service(self):
            # Test opening drive with existing service
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
                    found_share=True
            ok_(found_share, msg="Share not found in listing")

        def share_not_listed(self, resource, user):
            shares = resource.share_list()
            found_share = False
            for s in shares:
                if s[0] == user:
                    found_share=True
            ok_(not found_share, msg="Share found in listing")

        def test_ls(self):
            """Test that ls is working."""
            self.resource_listed(self.resource_one)
            self.resource_listed(self.resource_two)
            self.resource_listed(self.sheet.resource)

        def test_create_sheet(self):
            """Test codes ability to create sheets from existing resource."""
            s = pods.google.sheet(resource=self.resource_one)

        def test_delete(self):
            # Test that a file can be deleted and undeleted (using trash)
            self.resource_one.delete()
            self.resource_not_listed(self.resource_one)
            self.resource_one.undelete()
            self.resource_listed(self.resource_one)

        def test_share(self):
            """Test that resource can be shared."""
            self.resource_one.share(test_user)
            self.share_listed(self.resource_one, test_user, 'writer')
            self.resource_one.share_delete(test_user)
            self.share_not_listed(self.resource_one, test_user)

        def test_share_modify(self):
            """Test that sharing status can be changed."""
            self.resource_two.share(test_user)
            self.share_listed(self.resource_two, test_user, 'writer')
            self.resource_two.share_modify(test_user, 'reader')
            self.share_listed(self.resource_two, test_user, 'reader')

        def test_name_change(self):
            """Test that the name of the file on google drive can be changed."""
            new_name = "Testing Name 2"
            self.resource_one.update_name(new_name)
            eq_(new_name, self.resource_one.get_name(), msg="Name change has failed to take effect")


        def test_mime_type(self):
            "Test that mime_type of file is correct."
            eq_(self.sheet.resource.get_mime_type(), pods.google.sheet_mime, msg="Mime type of google spread sheet does not match expectation.")
