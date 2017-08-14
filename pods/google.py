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
                        f = open(os.path.join(keyfile))
                        self._oauthkey = json.load(f)
                        f.close()
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
        """Resource found on the google drive.
        :param id: the google id of the spreadsheet to open (default is None which creates a new spreadsheet).
        """
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

        :param worksheet_name: the worksheet in the spreadsheet to work with (default None which causes Sheet1 to be the name)
        :param title: the title of the spreadsheet (used if the spreadsheet is created for the first time)
        :param col_indent: the column indent to use in the spreadsheet.
        :type col_indent: int
        :param drive: the google drive client to use (default is None which performs a programmatic login)
        :param gs_client: the google spread sheet client login (default is none which causes a new client login)
        :param header: number of header rows in the document.
        :type header: int
        :param na_values: additional list containing entry types that are to be considered to be missing data (default is empty list).
        :type na_values: list
        :param dtype: Type name or dict of column -> type Data type for data or columns. E.g. {'a': np.float64, 'b': np.int32}
        :type dtype: dictonary
        :param raw_values: whether to read values rather than the formulae in the spreadsheet (default is False).
        :type raw_values: bool
        """
        def __init__(self, resource=None, gs_client=None, worksheet_name=None, index_field=None, col_indent=0, na_values=['nan'], dtype = {}, raw_values=False, header=1):


            source = 'ODS Gdata Bot'                
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']    
            self.raw_values = raw_values
            self.header = header
            self.index_field = None
            if type(na_values) is str:
                na_values = [na_values]
            self.na_values = na_values
            self.dtype = dtype
            
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
            self.col_indent = col_indent
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

        def add_sheet(self, worksheet_name, rows=100, cols=10):
            """Add a worksheet. To add and set to the current sheet use set_sheet_focus()."""
            self.sheet.add_worksheet(title=worksheet_name, rows=rows, cols=cols)
            self.worksheets = self.sheet.worksheets()

        def write(self, data_frame, comment=None):
            """
            Write a pandas data frame to a google document. This function will overwrite existing cells, but will not clear them first.

            :param data_frame: the data frame to write.
            :type data_frame: pandas.DataFrame
            :param comment: a comment to make at the top of the document (requres header>1
            :type comment: str
            """
            if comment is not None:
                if self.header==1:
                    raise ValueError('Comment will be overwritten by column headers')
                self.write_comment(comment)
                    
            self.write_headers(data_frame)
            self.write_body(data_frame)

        def augment(self, data_frame, columns, comment=None):
            """
            Augment is a special wrapper function for update that calls it
            with overwrite set to False. Use this command if you only want
            to make changes when the cell in the spreadsheet is empty.
            """
            self.update(data_frame, columns, comment, overwrite=False)

        def update(self, data_frame, columns=None, comment=None, overwrite=True):
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
            :param comment: comment to place in the top row of the header (requires header>1)
            :type comment: str
            :rtype: pandas.DataFrame

            .. Note:: Returns the data frame that was found in the spreadsheet.

            """
            if not data_frame.index.is_unique:
                raise ValueError("Index for data_frame is not unique in Google spreadsheet " + self.url)
            ss = self.read()
            if not ss.index.is_unique:
                raise ValueError("Index in sheet is not unique in Google spreadsheet " + self.url)
            if columns is None:
                columns = ss.columns
            if (len(set(ss.columns) - set(data_frame.columns))>0 or
                len(set(data_frame.columns) - set(ss.columns))>0):
                # TODO: Have a lazy option that doesn't mind this mismatch and accounts for it.
                raise ValueError('There is a mismatch between columns in online spreadsheet and the data frame we are using to update in Google spreadsheet ' + self.url)

            
            add_row = []
            remove_row = []
            update_triples = []
            # Compute necessary changes
            for index in data_frame.index:
                if index in ss.index:
                    for column in columns:
                        ss_val = ss[column][index]
                        df_val = data_frame[column][index]
                        if overwrite:
                            if not ss_val == df_val:
                                update_triples.append((index, column, df_val))
                        else:
                            if ((pd.isnull(ss_val) 
                                or ss_val == '') 
                                and not (pd.isnull(df_val)
                                         or df_val == '')):
                                update_triples.append((index, column, df_val))

                else:
                    add_row.append(index)

            if overwrite:
                for index in ss.index:
                    if index not in data_frame.index:
                        remove_row.append(index)

            index_to_add = []
            index_to_rem = []
            swap_list = []
                        
            swap_len = min(len(add_row), len(remove_row))
            row_change = len(add_row) - len(remove_row)

            if row_change > 0:
                index_to_add = add_row[-row_change:]

            if row_change < 0:
                index_to_rem = remove_row[row_change:]

            for add, rem in zip(add_row[:swap_len], remove_row[:swap_len]):
                swap_list.append((add, rem))
                
            cells = []
            for index,column,val in update_triples:
                cell = self._cell(index, column)
                if self.raw_values:
                    cell.input_value = val
                else:
                    cell.value = val
                cells.append(cell)

            for add, rem in swap_list:
                cells.extend(self._overwrite_row(index=rem,  new_index=add,
                                                 data_series=data_frame.loc[add]))
                
            if index_to_rem:
                cells.extend(self._delete_rows(index_to_rem))
            if index_to_add:
                cells.extend(self._add_rows(data_frame.loc[index_to_add]))
            
            self.worksheet.update_cells(cells)

        def _update_row_lookup(self, index):
            """Update the data series to be used as a look-up to find row associated with each index.
            :param index: the index names in order from the spreadsheet.
            :type index: list"""
            self.row_lookup = pd.Series(range(self.header+1, len(index)+self.header+1), index=index)

        def _update_col_lookup(self, columns):
            """Update the data series to be used as a look-up to find col associated with each column.
            :param column: the column names in order from the spreadsheet.
            :type column: list"""
            self.col_lookup = pd.Series(range(self.col_indent+1, len(columns)+self.col_indent+1), index=columns)

        def _cell(self, index, column):
            """Return the cell of the spreadsheet associated with the given index and column."""
            return self.worksheet.cell(self.row_lookup[index], self.col_lookup[column])

        
        def _overwrite_row(self, index, new_index, data_series):
            """Overwrite the given row in a spreadsheet with a data series."""
            cells = []
            for column in self.col_lookup.index:
                cell = self._cell(index, column)
                if column in data_series.index:
                    val = data_series[column]
                elif column == self.index_field:
                    val = new_index
                else:
                    val = None
                if self.raw_values:
                    cell.input_value = val
                else:
                    cell.value = val
                cells.append(cell)
            return cells

        def _delete_rows(self, index):
            """
            Delete a row of the spreadsheet.
            :param index: the row number to be deleted.
            :type index: index of pd.DataSeries"""
            if not index:
                return
            if type(index) is str:
                index = [index]
            minind = self.row_lookup[index].min()
                
            start = self.worksheet.get_addr_int(minind,
                                                self.col_lookup.min())
            end = self.worksheet.get_addr_int(self.row_lookup.max(),
                                              self.col_lookup.max())
            cells = self.worksheet.range(start + ':' + end)

            # download existing values
            data = defaultdict(lambda: defaultdict(str))
            for cell in cells:
                if self.raw_values:
                    val = cell.input_value
                else:
                    val = cell.value
                
                row = data.setdefault(int(cell.row), defaultdict(str))
                row[cell.col] = val
            # FutureWarning: sort is deprecated, use sort_values(inplace=True) for INPLACE sorting
            delete_rows = self.row_lookup[index].sort(inplace=False)
            # Find the ends of the banks to move up
            end_step = []
            for i, ind in enumerate(delete_rows.index):
                if i>0:
                    end_step.append(self.row_lookup[ind]-i)
            end_step.append(self.row_lookup.max()-len(index))

            # Move up each bank in turn.
            for i, ind in enumerate(delete_rows):
                for cell in cells:
                    if ((i==0 and cell.row <= end_step[i])
                        or (i>0 and cell.row <= end_step[i]
                            and cell.row>=end_step[i-1])):
                        val = data[cell.row+1+i][cell.col]
                        if self.raw_values:
                            cell.input_value = val
                        else:
                            cell.value = val

            # Delete exposed rows at bottom
            for cell in cells:
                if cell.row > end_step[-1]:
                    if self.raw_values:
                        cell.input_value = ''
                    else:
                        cell.value = ''

            # Update the row lookups
            for i, ind in enumerate(delete_rows.index):
                self.row_lookup[self.row_lookup>self.row_lookup[ind]] -= (i+1)
                self.row_lookup.drop(ind, inplace=True)

            return cells
        
            
        def _add_rows(self, data_frame):
            """
            Add a row to the spreadsheet.
            :param index: index of the row to be added.
            :type index: str or int (any valid index for a pandas.DataFrame)
            :param data_series: the entries of the row to be added.
            :type data_frame: pandas.DataFrame"""

            if type(data_frame) is pd.core.series.Series:
                data_frame = pd.DataFrame(data_frame).T
            maxind = self.row_lookup.max()
            for i, ind in enumerate(self.row_lookup.index):
                self.row_lookup[ind] = maxind+1+i
            start = self.worksheet.get_addr_int(maxind+1,
                                                self.col_lookup.min())
            end = self.worksheet.get_addr_int(maxind+data_frame.shape[0],
                                              self.col_lookup.max())
            cells = self.worksheet.range(start + ':' + end)
            for cell in cells:
                if cell.value != '':
                    raise ValueError("Overwriting non-empty cell in spreadsheet")
                i = cell.row - maxind-1
                index = data_frame.index[i]
                j = cell.col - self.col_lookup.min()-1
                if j < 0:
                    val = index
                else:
                    column = data_frame.columns[j]
                    val = data_frame[column][index]
                if self.raw_values:
                    cell.input_value = val
                else:
                    cell.value = val
            for i, ind in enumerate(data_frame.index):
                self.row_lookup[ind] = maxind+1+i
            return cells
                                
        def write_comment(self, comment, row=1, col=1):
            """Write a comment in the given cell"""
            self.worksheet.update_cell(row, col, comment)

        def write_body(self, data_frame, nan_val=''):
            """Write the body of a data frame to a google doc."""
            # query needs to be set large enough to pull down relevant cells of sheet.
            row_number = self.header
            start = self.worksheet.get_addr_int(row_number+1,
                                                self.col_indent+1)
            end = self.worksheet.get_addr_int(row_number+data_frame.shape[0], len(data_frame.columns)+self.col_indent+1)
            cells = self.worksheet.range(start + ':' + end)
            for cell in cells:
                if cell.col == self.col_indent + 1:
                    if cell.value != '':
                        raise ValueError("Non-empty cell be written to in Google sheet.")
                    # Write index
                    if self.raw_values:
                        cell.input_value = data_frame.index[cell.row-self.header-1]
                    else:
                        cell.value = data_frame.index[cell.row-self.header-1]
                else:
                    column = data_frame.columns[cell.col-self.col_indent-2]
                    index = data_frame.index[cell.row-self.header-1]
                    val = data_frame[column][index]
                    if type(val) is float:
                        if np.isnan(val):
                            val = nan_val
                    if self.raw_values:
                        cell.input_value = val
                    else:
                        cell.value = val
            self.worksheet.update_cells(cells)

        def write_headers(self, data_frame):
            """Write the headers of a data frame to the spreadsheet."""

            index_name = data_frame.index.name 
            if index_name == '' or index_name is None:
                index_name = 'index'
            headers = [index_name] + list(data_frame.columns)
            start = self.worksheet.get_addr_int(self.header, self.col_indent+1)
            end = self.worksheet.get_addr_int(self.header, len(data_frame.columns)+self.col_indent+1)
            # Select a range
            cells = self.worksheet.range(start + ':' + end)
            self._update_col_lookup(headers)
            for cell, value in zip(cells, headers):
                if cell.value != '':
                    raise ValueError("Error over-writing in non empty sheet")
                cell.value = value
            # Update in batch
            return self.worksheet.update_cells(cells)

        def read_headers(self):
            
            column_names=self.worksheet.row_values(self.header)[self.col_indent:]
            self._update_col_lookup(column_names)

            if self.index_field is None:
                # Return any column titled index or otherwise the first column
                index_col_num=next((i for i, column in enumerate(column_names) if column == 'index' or 'Index' or 'INDEX'), 0)
                self.index_field = column_names[index_col_num]
            elif self.index_field not in column_names:
                raise ValueError("Invalid index: " + self.index_field + " not present in sheet header row " + str(self.header) + ".")
            return column_names

        def read_body(self, use_columns=None):
            """
            Read in the body of a google sheet storing entries. 

            :param use_columns: return a subset of the columns.
            :type use_columns: list
            """
            # Find the index column number.
            if self.index_field in self.col_lookup:
                index_col_num = self.col_lookup[self.index_field]
            else:
                raise ValueError("Column " + self.index_field + " suggested for index not found in header row.")
                
                            
            # Assume the index column is full and count the entries.
            index = self.worksheet.col_values(index_col_num)[self.header:]
            self._update_row_lookup(index)
            
            num_entries = len(index)
            start = self.worksheet.get_addr_int(self.header+1,
                                                self.col_indent+1)
            end = self.worksheet.get_addr_int(self.header+num_entries,
                                              self.col_indent
                                              +len(self.col_lookup.index))
            body_cells = self.worksheet.range(start + ':' + end)

            data = {}
            for column in self.col_lookup.index:
                if not use_columns or column in use_columns:
                    data[column] = [None for i in range(num_entries)]

            for cell in body_cells:
                column = self.col_lookup.index[cell.col-self.col_indent-1]
                if not use_columns or column in use_columns:
                    if self.raw_values:
                        val = cell.input_value
                    else:
                        val = cell.value

                    if val is not None and val not in self.na_values:
                        if column in self.dtype.keys():
                            val = self.dtype[column](val)
                        else:
                            val = gspread.utils.numericise(val)
                            
                        data[column][cell.row-self.header-1]=val
            return data

        def read(self, names=None, use_columns=None):
            """
            Read in information from a Google document storing entries. Fields present are defined in 'names'

            :param names: list of names to give to the columns (in case they aren't present in the spreadsheet). Default None (for None, the column headers are read from the spreadsheet.
            :type names: list
            :param use_columns: return a subset of the columns.
            :type use_columns: list
            """

            # todo: need to check if something is written below the 'table' as this will be read (for example a rogue entry in the row below the last row of the data.
            column_names = self.read_headers()

            data = self.read_body(use_columns=use_columns)
            #if len(data[index_field])>len(set(data[index_field])):
            #    raise ValueError("Invalid index column, entries are not unique")
            return pd.DataFrame(data).set_index(self.index_field)

            #         except KeyError:
            #             print(("KeyError, unidentified key in ", self.worksheet_name, " in Google spreadsheet ", self.url))
            #             ans = input('Try and fix the error on the sheet and then return here. Error fixed (Y/N)?')
            #             if ans[0]=='Y' or ans[0] == 'y':
            #                 return self.read(names, header, na_values, read_values, dtype, use_columns, index_field)
            #             else:
            #                 raise KeyError("Unidentified key in " + self.worksheet_name + " in Google spreadsheet " + self.url)

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
            
#######################################################################
# Place methods here that are really associated with the resource. #
#######################################################################

        def set_title(self, title):
            """Change the title of the google spreadsheet."""
            self.resource.update_name(title)
            
        def get_title(self):
            """Get the title of the google spreadsheet."""
            return self.resource.get_name()

            
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

            self.resource.share_modify(user, share_type, send_notifications)
            

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
        



