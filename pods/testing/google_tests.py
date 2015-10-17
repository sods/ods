from nose.tools import assert_equals
import pods

# Google drive tests
def test_create_drive_access():
    d = pods.google.drive()
    e = pods.google.drive(credentials=d.credentials)
    f = pods.google.drive(service=e.service, http=e.http)
    

    f.list()

def test_create_drive_file():
    f = pods.google.file(name='Test file', mime_type=pods.google.sheet_mime)
    print(f.drive.list())

def test_create_sheet():
    s = pods.google.sheet()
