# Copyright 2014 Open Data Science Initiative and other authors. See AUTHORS.txt
# Licensed under the BSD 3-clause license (see LICENSE.txt)
from __future__ import print_function
from __future__ import absolute_import

import sys
import os

# Deal with raw_input in python
try:
    input = raw_input
except NameError:
    pass
    
import pandas as pd

from .config import *
import numpy as np

from . import notebook as nb

import pods

gspread_available=True
try:
    import gspread
    from collections import defaultdict
    from itertools import chain
    
    from oauth2client.client import SignedJwtAssertionCredentials
    import httplib2
    # easy_install --upgrade google-api-python-client
    from apiclient import errors
    from apiclient.discovery import build
    from apiclient.http import BatchHttpRequest
    
except ImportError:
    gspread_available=False

if gspread_available:
    import json
    import warnings
    sheet_mime = 'application/vnd.google-apps.spreadsheet'
    keyfile = os.path.expanduser(os.path.expandvars(config.get('google docs', 'oauth2_keyfile')))

    class drive:
        """
        Class for accessing a google drive and managing files.
        """
        def __init__(self, scope=None, credentials=None, http=None, service=None):
            # Get a google drive API connection.
            if service is None:
                if http is None:
                    if credentials is None:
                        self._oauthkey = json.load(open(os.path.join(keyfile)))
                        self.email = self._oauthkey['client_email']
                        self.key = bytes(self._oauthkey['private_key'], 'UTF-8')
                        if scope is None:
                            self.scope = ['https://www.googleapis.com/auth/drive']
                        else:
                            self.scope = scope
                        self.credentials = SignedJwtAssertionCredentials(self.email, self.key, self.scope)
                    else:
                        self.credentials = credentials
                        self.key = None
                        self.email = None
                    
                    http = httplib2.Http()
                    self.http = self.credentials.authorize(http)
                else:
                    self.http = http
                self.service = build('drive', 'v2', http=self.http)
            else:
                self.service = service

        def ls(self):
            """List all resources on the google drive"""
            results = []
            page_token = None
            while True:
                param = {}
                if page_token:
                    param['pageToken'] = page_token
                files = self.service.files().list(**param).execute()
                results.extend(files['items'])
                page_token = files.get('nexPageToken')
                if not page_token:
                    break
            files = []
            for result in results:
                if not result['labels']['trashed']:
                    files.append(pods.google.resource(id=result['id'], name=result['title'], mime_type=result['mimeType'], url=result['alternateLink'], drive=self))
            return files

        def _repr_html_(self):
            """Create a representation of the google drive for the notebook."""
            files = self.ls()
            output = '<p><b>Google Drive</b></p>'
            for file in files:
                output += file._repr_html_()
                
            
            return output

        
    class resource:
        """Resource found on the google drive."""
        def __init__(self, name=None, mime_type=None, url=None, id=None, drive=None):

            if drive is None:
                self.drive=pods.google.drive()
            else:
                self.drive = drive

            if id is None:
                if name is None:
                    name = "Google Drive Resource"
                # create a new sheet
                body = {'mimeType': mime_type,
                        'title': name}
                try:
                    self.drive.service.files().insert(body=body).execute(http=self.drive.http)
                except(errors.HttpError):
                    print("Http error")

                self._id=self.drive.service.files().list(q="title='" + name + "'").execute(http=self.drive.http)['items'][0]['id']
                self.name = name
                self.mime_type = mime_type
            else:                
                self._id=id
                if name is None:
                    self.get_name()
                else:
                    self.name = name
                if mime_type is None:
                    self.get_mime_type()
                else:
                    self.mime_type = mime_type
                if url is None:    
                    self.get_url()
                else:
                    self.url = url

            

        def delete(self, empty_bin=False):
            """Delete the file from drive."""
            if empty_bin:
                self.drive.service.files().delete(fileId=self._id).execute()
            else:
                self.drive.service.files().trash(fileId=self._id).execute()

        def undelete(self):
            """Recover file from the trash (if it's there)."""
            self.drive.service.files().untrash(fileId=self._id).execute()

            
        def share(self, users, share_type='writer', send_notifications=False, email_message=None):
            """
            Share a document with a given list of users.
            """
            if type(users) is str:
                users = [users]
            def batch_callback(request_id, response, exception):
                print("Response for request_id (%s):" % request_id)
                print(response)

                # Potentially log or re-raise exceptions
                if exception:
                    raise exception

            batch_request = BatchHttpRequest(callback=batch_callback)
            for count, user in enumerate(users):
                batch_entry = self.drive.service.permissions().insert(fileId=self._id, sendNotificationEmails=send_notifications, emailMessage=email_message,
                                                             body={
                                                                 'value': user,
                                                                 'type': 'user',
                                                                 'role': share_type
                                                             })
                batch_request.add(batch_entry, request_id="batch"+str(count))

            batch_request.execute()

        def share_delete(self, user):
            """
            Remove sharing from a given user.
            """
            permission_id = self._permission_id(user)
            self.drive.service.permissions().delete(fileId=self._id,
                                              permissionId=permission_id).execute()


        def share_modify(self, user, share_type='reader', send_notifications=False):
            """
            :param user: email of the user to update.
            :type user: string
            :param share_type: type of sharing for the given user, type options are 'reader', 'writer', 'owner'
            :type user: string
            :param send_notifications: 
            """
            if share_type not in ['writer', 'reader', 'owner']:
                raise ValueError("Share type should be 'writer', 'reader' or 'owner'")
            
            permission_id = self._permission_id(user)
            permission = self.drive.service.permissions().get(fileId=self._id, permissionId=permission_id).execute()
            permission['role'] = share_type
            self.drive.service.permissions().update(fileId=self._id, permissionId=permission_id, body=permission).execute()

        def _permission_id(self, user):
             
            return self.drive.service.permissions().getIdForEmail(email=user).execute()['id']
            
        def share_list(self):
            """
            Provide a list of all users who can access the document in the form of 
            """
            permissions = self.drive.service.permissions().list(fileId=self._id).execute()
                
            entries = []
            for permission in permissions['items']:
                entries.append((permission['emailAddress'], permission['role']))
            return entries

        def revision_history(self):
            """
            Get the revision history of the document from Google Docs.
            """
            for item in self.drive.service.revisions().list(fileId=self._id).execute()['items']:
                print(item['published'], item['selfLink'])
            
        def update_name(self, name):
            """Change the title of the file."""
            body = self.drive.service.files().get(fileId=self._id).execute()
            body['title'] = name
            body = self.drive.service.files().update(fileId=self._id, body=body).execute()
            self.name = name

        def get_mime_type(self):
            """Get the mime type of the file."""

            details=self.drive.service.files().list(q="title='" + self.name + "'").execute(http=self.drive.http)['items'][0]
            self.mime_type = details['mimeType']
            return self.mime_type

        def get_name(self):
            """Get the title of the file."""
            self.name = self.drive.service.files().get(fileId=self._id).execute()['title']
            return self.name

        def get_url(self):
            self.url = self.drive.service.files().get(fileId=self._id).execute()['alternateLink']
            return self.url
        
        def update_drive(self, drive):
            """Update the file's drive API service."""
            self.drive = drive

        def _repr_html_(self):
            output = '<p><b>{title}</b> at <a href="{url}" target="_blank">this url.</a> ({mime_type})</p>'.format(url=self.url, title=self.name, mime_type=self.mime_type)
            return output

    class sheet():
        """
        Class for interchanging information between google spreadsheets and pandas data frames. The class manages a spreadsheet.

        :param spreadsheet_key: the google key of the spreadsheet to open (default is None which creates a new spreadsheet).
        :param worksheet_name: the worksheet in the spreadsheet to work with (default None which causes Sheet1 to be the name)
        :param title: the title of the spreadsheet (used if the spreadsheet is created for the first time)
        :param column_indent: the column indent to use in the spreadsheet.
        :type column_indent: int
        :param drive: the google drive client to use (default is None which performs a programmatic login)
        :param gs_client: the google spread sheet client login (default is none which causes a new client login)
        """
        def __init__(self, resource=None, gs_client=None, worksheet_name=None, column_indent=0):

            source = 'ODS Gdata Bot'                
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']    

            if resource is None:
                drive = pods.google.drive(scope=scope)
                self.resource = pods.google.resource(drive=drive, name="Google Sheet", mime_type=sheet_mime)
            else:
                if 'https://spreadsheets.google.com/feeds' not in resource.drive.scope:
                    drive = pods.google.drive(scope=scope)
                    resource.update_drive(drive)
                self.resource = resource
                
            # Get a Google sheets client
            if gs_client is None:
                self.gs_client = gspread.authorize(self.resource.drive.credentials)
            else:
                self.gs_client = gs_client

            self.sheet = self.gs_client.open_by_key(self.resource._id)

            if worksheet_name is None:
                self.worksheet = self.sheet.worksheets()[0]
            else:
                self.worksheet = self.sheet.worksheet(title=worksheet_name)
            self.column_indent = column_indent
            self.url = 'https://docs.google.com/spreadsheets/d/' + self.resource._id + '/'


#############################################################################
# Place methods here that are really associated with individual worksheets. #
#############################################################################

        def change_sheet_name(self, title):
            """Change the title of the current worksheet to title."""
            raise NotImplementedError
            raise ValueError("Can't find worksheet " + self.worksheet_name + " to change the name in Google spreadsheet " + self.url)
                

        def set_sheet_focus(self, worksheet_name):
            """Set the current worksheet to the given name. If the name doesn't exist then create the sheet using sheet.add_worksheet()"""
            self.worksheets = self.sheet.worksheets()
            # if the worksheet is set to None default to first sheet, warn if it's name is not "Sheet1".
            names = [worksheet.title for worksheet in worksheets]
            if worksheet_name is None:
                self.worksheet_name = self.worksheets[0].title
                if len(self.worksheets)>1 and self.worksheet_name != 'Sheet1':
                    print("Warning, multiple worksheets in this spreadsheet and no title specified. Assuming you are requesting the sheet called '{sheetname}'. To surpress this warning, please specify the sheet name.".format(sheetname=self.worksheet_name))
            else:
                if worksheet_name not in names:
                    # create new worksheet here.
                    self.sheet.add_worksheet(title=worksheet_name)
                    self.worksheet_name = worksheet_name
                else:
                    self.worksheet_name = worksheet_name
                    self.worksheet = self.sheet.set_worksheet(self.worksheet_name)
            # Get list of ids from the spreadsheet
            self.worksheet = self.sheet(self.worksheet_name)

        def add_sheet(self, worksheet_name, rows=100, columns=10):
            """Add a worksheet. To add and set to the current sheet use set_sheet_focus()."""
            self.sheet.add_worksheet(title=worksheet_name, rows=rows, cols=columns)
            self.worksheets = self.sheet.worksheets()

        def write(self, data_frame, header=None, comment=None):
            """
            Write a pandas data frame to a google document. This function will overwrite existing cells, but will not clear them first.

            :param data_frame: the data frame to write.
            :type data_frame: pandas.DataFrame
            :param header: number of header rows in the document.
            :type header: int
            :param comment: a comment to make at the top of the document (requres header>1
            :type comment: str
            """
            if comment is not None:
                if header is None:
                    header=2
                elif header==1:
                    raise ValueError('Comment will be overwritten by column headers')
                self.write_comment(comment)
            else:
                if header is None:
                    header=1
            self.write_headers(data_frame, header)
            self.write_body(data_frame, header)

        def augment(self, data_frame, columns, header=1, comment=None):
            """
            Augment is a special wrapper function for update that calls it
            with overwrite set to False. Use this command if you only want
            to make changes when the cell in the spreadsheet is empty.
            """
            self.update(data_frame, columns, header, comment, overwrite=False)

        def update(self, data_frame, columns=None, header=1, comment=None, overwrite=True):
            """
            Update a google document with a given data frame. The
            update function assumes that the columns of the data_frame and
            the google document match, and that an index in either the
            google document or the local data_frame identifies one row
            uniquely. If columns is provided as a list then only the
            listed columns are updated.

            **Notes**

            :data_frame : data frame to update the spreadsheet with.
            :type data_frame: pandas.DataFrame
            :param columns: which columns are updated in the spreadsheet (by default all columns are updated)
            :type columns: list
            :param hearder_rows: how many rows are in the header (including the column headers). By default there is 1 row. 
            :type header: int
            :param comment: comment to place in the top row of the header (requires header>1)
            :type comment: str
            :rtype: pandas.DataFrame

            .. Note:: Returns the data frame that was found in the spreadsheet.

            """
            if not data_frame.index.is_unique:
                raise ValueError("Index for data_frame is not unique in Google spreadsheet " + self.url)
            ss = self.read(header=header)
            if not ss.index.is_unique:
                raise ValueError("Index in google doc is not unique in Google spreadsheet " + self.url)
            if columns is None:
                columns = ss.columns
            if (len(set(ss.columns) - set(data_frame.columns))>0 or
                len(set(data_frame.columns) - set(ss.columns))>0):
                # TODO: Have a lazy option that doesn't mind this mismatch and accounts for it.
                raise ValueError('There is a mismatch between columns in online spreadsheet and the data frame we are using to update in Google spreadsheet ' + self.url)
            add_row = []
            remove_row = []
            update_cell = []
            # Compute necessary changes
            for index in data_frame.index:
                if index in ss.index:
                    for column in columns:
                        if overwrite:
                            if not ss[column][index] == data_frame[column][index]:
                                update_cell.append((index, column))
                        else:
                            if ((pd.isnull(ss[column][index]) 
                                or ss[column][index] == '') 
                                and not (pd.isnull(data_frame[column][index])
                                         or data_frame[column][index] == '')):
                                update_cell.append((index, column))

                else:
                    add_row.append(index)
            if overwrite:
                for index in ss.index:
                    if index not in data_frame.index:
                        remove_row.append(index)


            row_number = header+1

            self.row_batch_size = 10
            query = gdata.spreadsheet.service.CellQuery()
            query.return_empty = "true" 
            query.min_col = str(self.column_indent+1) 
            query.max_col = str(len(ss.columns)+1+self.column_indent)
            query.min_row = str(row_number)
            query.max_row = str(row_number + self.row_batch_size)
            cells = self._get_cell_feed(query=query)

            batchRequest = gdata.spreadsheet.SpreadsheetsCellsFeed()
            counter = 0
            row_to_delete = []
            row_number = 1
            for index, row in ss.iterrows():
                if counter>=len(cells.entry):
                    # Update current block
                    updated = self.gd_client.ExecuteBatch(batchRequest, cells.GetBatchLink().href)
                    # pull down new batch of cells.
                    query.min_row = str(row_number)
                    query.max_row = str(row_number + self.row_batch_size)
                    cells = self._get_cell_feed(query=query)
                    batchRequest = gdata.spreadsheet.SpreadsheetsCellsFeed()
                    counter = 0
                current_index = cells.entry[counter].cell.inputValue 
                row_number = int(cells.entry[counter].cell.row) + 1

                if current_index in remove_row:
                    v = int(cells.entry[counter].cell.row)-header-1
                    row_to_delete.append(v)
                    print("Warning deleting row indexed by '" + current_index + "' from " + cells.entry[counter].cell.row + " currently! Not comprehensively tested. Best guess is that row to delete is " + str(v) + " in Google spreadsheet " + self.url)
                    ans = input("Delete row (Y/N)?")
                    if len(ans)==0 or (not ans[0]=='Y' and not ans[0] == 'y'):
                        raise ValueError("Not willing to delete row.")
                    counter+=len(row)
                    continue
                else:
                    counter+=1
                for current_column, entry in row.items():
                    if (current_index, current_column) in update_cell:
                        val = data_frame[current_column][index]
                        if not pd.isnull(val):
                            v = []
                            try:
                                v = str(val)
                            except UnicodeDecodeError:
                                v = str(val)
                            cells.entry[counter].cell.inputValue = v
                        else:
                            cells.entry[counter].cell.inputValue = ''
                        batchRequest.AddUpdate(cells.entry[counter])
                    counter+=1
            updated = self.gd_client.ExecuteBatch(batchRequest, cells.GetBatchLink().href)
            # Delete the rows to be removed.
            for row in sorted(row_to_delete, reverse=True):
                print(("Delete row ", row))
                self._delete_row(row)
            # Insert the rows to be added
            for index in add_row:
                self._add_row(index, data_frame.loc[index])

        def _delete_row(self, row_number):
            """
            Delete a row of the spreadsheet.
            :param row_number: the row number to be deleted.
            :type row_number: int"""
            raise NotImplementedError("Delete row is not yet implemented in gspread")

        def _add_row(self, index, data_series):
            """
            Add a row to the spreadsheet.
            :param index: index of the row to be added.
            :type index: str or int (any valid index for a pandas.DataFrame)
            :param data_series: the entries of the row to be added.
            :type data_series: pandas.Series"""
            raise NotImplementedError("Add row not yet implemented in gspread interface")
            # dict = {}
            # dict['index'] = index
            # for column, entry in data_series.items():
            #     if not pd.isnull(entry):
            #         val = []
            #         try:
            #             val = str(entry)
            #         except UnicodeDecodeError:
            #             val = str(entry)
            #         dict[column] = val
            # self.worksheet.insert_row(dict, index)


        def write_comment(self, comment, row=1, column=1):
            """Write a comment in the given cell"""
            self.worksheet.update_cell(row, column, comment)

        def write_body(self, data_frame, header=1):
            """Write the body of a data frame to a google doc."""
            # query needs to be set large enough to pull down relevant cells of sheet.
            row_number = header
            start = self.worksheet.get_addr_int(row_number+1,
                                                self.column_indent+1)
            end = self.worksheet.get_addr_int(row_number+data_frame.shape[0], len(data_frame.columns)+self.column_indent+1)
            cell_list = self.worksheet.range(start + ':' + end)
            for cell in cell_list:
                if cell.col == self.column_indent + 1:
                    # Write index
                    cell.value = data_frame.index[cell.row-header-1]
                else:
                    column = data_frame.columns[cell.col-self.column_indent-2]
                    index = data_frame.index[cell.row-header-1]
                    cell.value = data_frame[column][index]
            self.worksheet.update_cells(cell_list)

        def write_headers(self, data_frame, header=1):
            """Write the headers of a data frame to the spreadsheet."""

            index_name = data_frame.index.name 
            if index_name == '' or index_name is None:
                index_name = 'index'
            headers = [index_name] + list(data_frame.columns)
            start = self.worksheet.get_addr_int(header, self.column_indent+1)
            end = self.worksheet.get_addr_int(header, len(data_frame.columns)+self.column_indent+1)
            # Select a range
            cell_list = self.worksheet.range(start + ':' + end)
            
            for cell, value in zip(cell_list, headers):
                cell.value = value

            # Update in batch
            return self.worksheet.update_cells(cell_list)

        def read(self, names=None, header=1, na_values=[], read_values=False, dtype={}, usecols=None, index_field=None):
            """
            Read in information from a Google document storing entries. Fields present are defined in 'names'

            :param names: list of names to give to the columns (in case they aren't present in the spreadsheet). Default None (for None, the column headers are read from the spreadsheet.
            :type names: list
            :param header: number of rows to use as header (default is 1).
            :type header: int
            :param na_values: additional list containing entry types that are to be considered to be missing data (default is empty list).
            :type na_values: list
            :param read_values: whether to read values rather than the formulae in the spreadsheet (default is False).
            :type read_values: bool
            :param dtype: Type name or dict of column -> type Data type for data or columns. E.g. {'a': np.float64, 'b': np.int32}
            :type dtype: dictonary
            :param usecols: return a subset of the columns.
            :type usecols: list
            """

            # todo: need to check if something is written below the 'table' as this will be read (for example a rogue entry in the row below the last row of the data.
            #dictvals = self.worksheet.get_all_records(empty2zero=False, head=header)

            cells = self.worksheet._fetch_cells()

            # code modified from gspread (https://github.com/burnash/gspread/blob/master/gspread/models.py)
            # defaultdicts fill in gaps for empty rows/cells not returned by gdocs
            rows = defaultdict(lambda: defaultdict(str))
            for cell in cells:
                row = rows.setdefault(int(cell.row), defaultdict(str))
                if read_values:
                    row[cell.col] = cell.value
                else:
                    row[cell.col] = cell.input_value

            # we return a whole rectangular region worth of cells, including
            # empties
            if not rows:
                return []

            all_row_keys = chain.from_iterable(row.keys() for row in rows.values())
            rect_cols = range(1, max(all_row_keys) + 1)
            rect_rows = range(1, max(rows.keys()) + 1)

            data = [[rows[i][j] for j in rect_cols] for i in rect_rows]
            idx = header - 1
            keys = data[idx]
            values = [gspread.utils.numericise_all(row, False) for row in data[idx + 1:]]

            dictvals= [dict(zip(keys, row)) for row in values]
            if index_field is None:
                if 'index' in dictvals[0].keys():
                    index_field = 'index'
                elif 'Index' in dictvals[0].keys():
                    index_field = 'Index'
                elif 'INDEX' in dictvals[0].keys():
                    index_field = 'INDEX'
            
            if index_field is not None and index_field in dictvals[0].keys():
                return pd.DataFrame(dictvals).set_index(index_field)
            else:
                print("Warning no such column name for index in sheet. Generating new index")
                return pd.DataFrame(dictvals)

            #         except KeyError:
            #             print(("KeyError, unidentified key in ", self.worksheet_name, " in Google spreadsheet ", self.url))
            #             ans = input('Try and fix the error on the sheet and then return here. Error fixed (Y/N)?')
            #             if ans[0]=='Y' or ans[0] == 'y':
            #                 return self.read(names, header, na_values, read_values, dtype, usecols, index_field)
            #             else:
            #                 raise KeyError("Unidentified key in " + self.worksheet_name + " in Google spreadsheet " + self.url)

#######################################################################
# Place methods here that are really associated with the spreadsheet. #
#######################################################################

        def set_title(self, title):
            """Change the title of the google spreadsheet."""
            self.resource.update_name(title)
            
        def get_title(self):
            """Get the title of the google spreadsheet."""
            return self.resource.get_name()

        def delete_sheet(self, worksheet_name):
            """Delete the worksheet with the given name."""
            self.sheet.del_worksheet(entry)

        def update_sheet_list(self):
            """Update object with the worksheet feed and the list of worksheets, can only be run once there is a gspread client (gs_client) in place. Needs to be rerun if a worksheet is added."""
            self.worksheets = self.sheet._sheet_list

        def _repr_html_(self):
            if self.ispublished(): #self.document.published.tag=='published':
                output = '<p><b>{title}</b> at <a href="{url}" target="_blank">this url.</a>\n</p>'.format(url=self.url, title=self.get_title())
                url = self.url + '/pubhtml?widget=true&amp;headers=false' 
                return output + nb.iframe_url(url, width=500, height=300)
            else:
                output = '<p><b>{title}</b> at <a href="{url}" target="_blank">this url.</a>\n</p>'.format(url=self.url, title=self.get_title())
                return output + self.read()._repr_html_()
                #return None
            

        def show(self, width=400, height=200):
            """If the IPython notebook is available, and the google
            spreadsheet is published, then the spreadsheet is displayed
            centrally in a box."""
            if self.ispublished():
                try:
                    from IPython.display import HTML
                    url = self.url + '/pubhtml?widget=true&amp;headers=false' 
                    nb.iframe_url(url, width=width, height=height)
                except ImportError:
                    print(ds.url)
                else:
                    raise
            
        def share(self, users, share_type='writer', send_notifications=False, email_message=None):
            """
            Share a document with a given list of users.
            """
            warnings.warn("Sharing should be performed on the drive class.", DeprecationWarning)
            self.resource.share(users, share_type, send_notifications, email_message)

        def share_delete(self, user):
            """
            Remove sharing from a given user.
            """
            warnings.warn("Sharing should be performed on the drive class.", DeprecationWarning)
            return self.resource.share_delete(user)

        def share_modify(self, user, share_type='reader', send_notifications=False):
            """
            :param user: email of the user to update.
            :type user: string
            :param share_type: type of sharing for the given user, type options are 'reader', 'writer', 'owner'
            :type user: string
            :param send_notifications: 
            """
            warnings.warn("Sharing should be performed on the drive class.", DeprecationWarning)

            return self.resource.share_modify(user, share_type, send_notifications)
            

        def _permission_id(self, user):
             
            return self.resource.service.permissions().getIdForEmail(email=user).execute()['id']
            
        def share_list(self):
            """
            Provide a list of all users who can access the document in the form of 
            """
            warnings.warn("Sharing should be performed on the drive class.", DeprecationWarning)

            return self.resource.share_list()

        def revision_history(self):
            """
            Get the revision history of the document from Google Docs.
            """
            warnings.warn("Revision history should be performed on the drive class.", DeprecationWarning)
            return self.resource.revision_history()

        def ispublished(self):
            """Find out whether or not the spreadsheet has been published."""
            return self.resource.drive.service.revisions().list(fileId=self.resource._id).execute()['items'][-1]['published']
        



