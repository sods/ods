# Copyright 2014 Open Data Science Initiative and other authors. See AUTHORS.txt
# Licensed under the BSD 3-clause license (see LICENSE.txt)


import pandas as pd
import gdata.spreadsheet.service # Requires python-gdata on Ubuntu
import urlparse
import os

from config import *

email = config.get('google docs', 'user')
password = config.get('google docs', 'password')

class sheet():
    """
    Class for interchanging information between google spreadsheets and pandas data frames. The class manages a spreadsheet.

    :param spreadsheet_key: the google key of the spreadsheet to open (default is None which creates a new spreadsheet).
    :param worksheet_name: the worksheet in the spreadsheet to work with (default 'Sheet1')
    :param title: the title of the spreadsheet (used if the spreadsheet is created for the first time)
    :param column_indent: the column indent to use in the spreadsheet.
    :type column_indent: int
    :param gd_client: the google spreadsheet service client to use (default is NOne which performs a programmatic login)
    :param docs_client: the google docs login client (default is none which causes a new client login)

    """
    def __init__(self, spreadsheet_key=None, worksheet_name='Sheet1', title='Google Spreadsheet', column_indent=0, gd_client=None, docs_client=None):
        import gdata.docs.client
        source = 'NIPS Review System'
        if docs_client is None:
            self.docs_client = gdata.docs.client.DocsClient()
            self.docs_client.client_login(email, password, source)
        else:
            self.docs_client = docs_client
        if spreadsheet_key is None:
            # need to create the document
            #self.gd_client = gdata.docs.client.DocsClient()
            document = gdata.docs.data.Resource(type='spreadsheet', title=title)
            worksheet_name = 'Sheet1'
            self.document = self.docs_client.create_resource(document)
            self._key = self.document.get_id().split("%3A")[1]
        else:
            
            self._key = spreadsheet_key
            self.document = self.docs_client.GetResourceById(spreadsheet_key)
            # document exists already

        self.worksheet_name = worksheet_name
        
        if gd_client is None:
            self.gd_client = gdata.spreadsheet.service.SpreadsheetsService()
            self.gd_client.email = email
            self.gd_client.password = password
            self.gd_client.source = source
            self.gd_client.ProgrammaticLogin()
        else:
            self.gd_client=gd_client

        # Obtain list feed of specific worksheet. 
        self.feed = self.gd_client.GetWorksheetsFeed(key=self._key)
        self.id_dict = self.worksheet_ids()

        # Get list of ids from the spreadsheet
       
        self.worksheet_id = self.id_dict[self.worksheet_name]

        self.column_indent = column_indent
        self.url = 'https://docs.google.com/spreadsheets/d/' + self._key + '/'
    def show(self, width=400, height=200):
        """If the IPython notebook is available, and the google
        spreadsheet is published, then the spreadsheet is displayed
        centrally in a box."""

        try:
            from IPython.display import HTML
            HTML('<center><iframe src=' + ds.url + '/pubhtml?widget=true&amp;headers=false width=' + str(width) + ' height='+ str(height) +'></iframe></center>')
        except:
            print ds.url

    def worksheet_ids(self):
        def _id(entry):
            split = urlparse.urlsplit(entry.id.text)
            return os.path.basename(split.path)
        return dict([(entry.title.text, _id(entry)) for entry in self.feed.entry])

    def share(self, users, share_type='writer', send_notifications=False):
        # share a document with the given gmail user.
        for user in users:
            acl_entry = gdata.docs.data.AclEntry(
                scope=gdata.acl.data.AclScope(value=user, type='user'),
                role=gdata.acl.data.AclRole(value=share_type),
                )
            acl2 = self.docs_client.AddAclEntry(self.document, acl_entry, send_notifications=send_notifications)
        
    def write(self, data_frame, header_rows=None, comment=None):
        """Write a data frame to a google document. This function will overwrite existing cells, but will not clear them first."""
        if comment is not None:
            if header_rows is None:
                header_rows=2
            elif header_rows==1:
                raise ValueError('Comment will be overwritten by column headers')
            self.write_comment(comment)
        else:
            if header_rows is None:
                header_rows=1
        self.write_headers(data_frame, header_rows)
        self.write_body(data_frame, header_rows)
    def augment(self, data_frame, columns, header_rows=1, comment=None):
        """Augment is a special wrapper function for update that calls it with overwrite set to False. Use this command if you only want to make changes when the cell in the spreadsheet is empty."""
        self.update(data_frame, columns, header_rows, comment, overwrite=False)
    def update(self, data_frame, columns=None, header_rows=1, comment=None, overwrite=True):
        """Update a google document with a given data frame. The
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
        :type header_rows: int
        :param comment: comment to place in the top row of the header (requires header_rows>1)
        :type comment: str
        :rtype: pandas.DataFrame

        .. Note:: Returns the data frame that was found in the spreadsheet.

        """
        ss = self.read(header_rows=header_rows)
        if columns is None:
            columns = ss.columns
        if (len(set(ss.columns) - set(data_frame.columns))>0 or
            len(set(data_frame.columns) - set(ss.columns))>0):
            raise ValueError('There is a mismatch between columns in online spreadsheet and the data frame we are using to update.')
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


        row_number = header_rows+1

        self.row_batch_size = 10
        query = gdata.spreadsheet.service.CellQuery()
        query.return_empty = "true" 
        query.min_col = str(self.column_indent+1) 
        query.max_col = str(len(ss.columns)+1+self.column_indent)
        query.min_row = str(row_number)
        query.max_row = str(row_number + self.row_batch_size)
        cells = self.gd_client.GetCellsFeed(self._key, wksht_id=self.worksheet_id, query=query)
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
                cells = self.gd_client.GetCellsFeed(self._key, wksht_id=self.worksheet_id, query=query)
                batchRequest = gdata.spreadsheet.SpreadsheetsCellsFeed()
                counter = 0
            current_index = cells.entry[counter].cell.inputValue 
            row_number = int(cells.entry[counter].cell.row) + 1
            
            if current_index in remove_row:
                v = int(cells.entry[counter].cell.row)-header_rows
                row_to_delete.append(v)
                prp
                counter+=len(row)
                continue
            else:
                counter+=1
            for current_column, entry in row.iteritems():
                if (current_index, current_column) in update_cell:
                    val = data_frame[current_column][index]
                    if not pd.isnull(val):
                        cells.entry[counter].cell.inputValue = str(val)
                    else:
                        cells.entry[counter].cell.inputValue = ''
                    batchRequest.AddUpdate(cells.entry[counter])
                counter+=1
        updated = self.gd_client.ExecuteBatch(batchRequest, cells.GetBatchLink().href)
        # Delete the rows to be removed.
        for row in sorted(row_to_delete, reverse=True):
            self._delete_row(row)
        # Insert the rows to be added
        for index in add_row:
            self._add_row(index, data_frame.loc[index])
        
        return ss
    def delete_entry(self, index):
        """Delete a row by index from the online spreadsheet.

        :param index: the index of the entry to be deleted.
        : type index: str or int (any valid index for a pandas.DataFrame).
        """
        pass
    def _delete_row(self, row_number):
        """Delete a row of the spreadsheet.
        :param row_number: the row number to be deleted.
        :type row_number: int"""
        list_feed = self.gd_client.GetListFeed(self._key, self.worksheet_id)
        self.gd_client.DeleteRow(list_feed.entry[row_number])

    def _add_row(self, index, data_series):
        """Add a row to the spreadsheet.
        :param index: index of the row to be added.
        :type index: str or int (any valid index for a pandas.DataFrame)
        :param data_series: the entries of the row to be added.
        :type data_series: pandas.Series"""
        dict = {}
        dict['index'] = index
        for column, entry in data_series.iteritems():
            if not pd.isnull(entry):
                dict[column] = str(entry)
            self.gd_client.InsertRow(dict, self._key, self.worksheet_id)


    def write_comment(self, comment, row=1, column=1):
        """Write a comment in the given cell"""
        query = gdata.spreadsheet.service.CellQuery()
        query.return_empty = "true" 
        query.min_col = str(column) 
        query.max_col = str(column)
        query.min_row = str(row)
        query.max_row = str(row)
        cells = self.gd_client.GetCellsFeed(self._key, wksht_id=self.worksheet_id, query=query)
        batchRequest = gdata.spreadsheet.SpreadsheetsCellsFeed()
        cells.entry[0].cell.inputValue = comment
        batchRequest.AddUpdate(cells.entry[0])
        updated = self.gd_client.ExecuteBatch(batchRequest, cells.GetBatchLink().href)
        
    def write_body(self, data_frame, header_rows):
        """Write the body of a data frame to a google doc."""
        # query needs to be set large enough to pull down relevant cells of sheet.
        row_number = header_rows+1
        self.row_batch_size = 10

        query = gdata.spreadsheet.service.CellQuery()
        query.return_empty = "true" 
        query.min_col = str(self.column_indent+1) 
        query.max_col = str(len(data_frame.columns)+1+self.column_indent)
        query.min_row = str(row_number)
        query.max_row = str(row_number + self.row_batch_size)
        cells = self.gd_client.GetCellsFeed(self._key, wksht_id=self.worksheet_id, query=query)
        batchRequest = gdata.spreadsheet.SpreadsheetsCellsFeed()
        counter = 0
        for index, row in data_frame.iterrows():
            if counter>=len(cells.entry):
                # Update current block
                row_number = int(cells.entry[counter-1].cell.row) + 1
                updated = self.gd_client.ExecuteBatch(batchRequest, cells.GetBatchLink().href)
                # pull down new batch of cells.
                query.min_row = str(row_number)
                query.max_row = str(row_number + self.row_batch_size)
                cells = self.gd_client.GetCellsFeed(self._key, wksht_id=self.worksheet_id, query=query)
                batchRequest = gdata.spreadsheet.SpreadsheetsCellsFeed()
                counter = 0
            cells.entry[counter].cell.inputValue = str(index)
            batchRequest.AddUpdate(cells.entry[counter])
            counter+=1
            for entry in row:
                if not pd.isnull(entry):
                    cells.entry[counter].cell.inputValue = str(entry)
                batchRequest.AddUpdate(cells.entry[counter])
                counter+=1
        updated = self.gd_client.ExecuteBatch(batchRequest, cells.GetBatchLink().href)

    def write_headers(self, data_frame, header_rows=1):
        """Write the headers of a data frame to the spreadsheet."""
        # query needs to be set large enough to pull down relevant cells of sheet.
        query = gdata.spreadsheet.service.CellQuery()
        query.return_empty = "true" 
        query.min_row = str(header_rows)
        query.max_row = query.min_row
        query.min_col = str(self.column_indent+1) 
        query.max_col = str(len(data_frame.columns)+self.column_indent+1) 

        cells = self.gd_client.GetCellsFeed(self._key, wksht_id=self.worksheet_id, query=query)
        
        batchRequest = gdata.spreadsheet.SpreadsheetsCellsFeed()
        index_name = data_frame.index.name 
        if index_name == '' or index_name is None:
            index_name = 'index'
        headers = [index_name] + list(data_frame.columns)
        for i, column in enumerate(headers):
            cells.entry[i].cell.inputValue = column
            batchRequest.AddUpdate(cells.entry[i])

        return self.gd_client.ExecuteBatch(batchRequest, cells.GetBatchLink().href)

    def read(self, column_fields=None, header_rows=1, nan_values=[]):
        """Read in information from a Google document storing entries. Fields present are defined in 'column_fields'"""

        # todo: need to check if something is written below the 'table' as this will be read (for example a rogue entry in the row below the last row of the data.
        entries_dict = {}
        index_dict = {}
        cells =  self.gd_client.GetCellsFeed(self._key, self.worksheet_id)
        read_column_fields = False
        if column_fields is None:
            read_column_fields = True
            column_fields = {}
        for myentry in cells.entry:
            col = myentry.cell.col
            row = myentry.cell.row
            value = myentry.cell.inputValue
            if int(row)<header_rows:
                continue
            if int(row)==header_rows:
                if read_column_fields:
                    # Read the column titles for the fields.
                    fieldname = value.strip()
                    if fieldname in column_fields.values():
                        raise ValueError("Field name duplicated in header")
                    else:
                        column_fields[col] = fieldname
                continue

            if not row in entries_dict:
                entries_dict[row] = {}

            if col in column_fields:
                field = column_fields[col]
            else:
                field = col
            
            # These should move down to inheriting class of drive_store
            if field.lower() == 'index':
                index_dict[row] = value.strip()
            else:
                if not value.strip() in nan_values:
                    val = value.strip()
                    try:
                        a = float(val)
                    except ValueError:
                        entries_dict[row][field] = val
                    else:
                        try:
                            a = int(a)
                        except ValueError:
                            entries_dict[row][field] = a
                        else:
                            if a == int(a):
                                entries_dict[row][field] = int(a)
                            else:
                                entries_dict[row][field] = a


                
        entries = []
        index = []
        for key in sorted(entries_dict.keys(), key=int):
            entries.append(entries_dict[key])
            if len(index_dict)>0:
                index.append(index_dict[key])
                
        if len(index)>0:
            entries = pd.DataFrame(entries, index=index)
        else:
            entries = pd.DataFrame(entries)
        if len(column_fields)>0:
            for field in column_fields.values():
                if field not in list(entries.columns) + ['index']:
                    entries[field] = ''
            column_order = []
            for key in sorted(column_fields, key=int):
                column_order.append(column_fields[key])
            if 'index' in column_order:
                column_order.remove('index')
            entries = entries[column_order]
                
        return entries
