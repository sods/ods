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
            self.document = self._get_resource_feed()
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
        self.feed = self._get_worksheet_feed()
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
        except ImportError:
            print ds.url
        else:
            raise

    def worksheet_ids(self):
        def _id(entry):
            split = urlparse.urlsplit(entry.id.text)
            return os.path.basename(split.path)
        return dict([(entry.title.text, _id(entry)) for entry in self.feed.entry])

    def share(self, users, share_type='writer', send_notifications=False):
        """
        Share a document with a given list of users.
        """
        # share a document with the given list of users.
        for user in users:
            acl_entry = gdata.docs.data.AclEntry(
                scope=gdata.acl.data.AclScope(value=user, type='user'),
                role=gdata.acl.data.AclRole(value=share_type),
                )
            acl2 = self.docs_client.AddAclEntry(self.document, acl_entry, send_notifications=send_notifications)
    
    def _get_acl_entry(self, user):
        """
        Return the acl entry associated with a given user name.
        """
        acl_feed = self._get_acl_feed()
        for acl_entry in acl_feed.entry:
            if acl_entry.scope.value == user:
                return acl_entry
        raise ValueError("User: " + user + " not in the acl feed for this resource.")


    def share_delete(self, user):
        """
        Remove sharing from a given user.
        """
        acl_entry = self._get_acl_entry(user)
        return self.docs_client.DeleteAclEntry(acl_entry)
            
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
            
        acl_entry = self._get_acl_entry(user)# update ACL entry
        
        #acl_entry.role.value = share_type
        # According to Ali Afshar you need to remove the etag (https://groups.google.com/forum/#!msg/google-documents-list-api/eFSmo14nDLA/Oo4SjePHZd8J), can't work out how though!
        #etag_element = acl_entry.find('etag')
        #acl_entry.remove(etagelement)
        #self.docs_client.UpdateAclEntry(acl_entry, sent_notifications=send_notifications)
        # Hack: delete and re-add.
        self.share_delete(acl_entry)
        self.share([user], share_type, send_notifications)

    def share_list(self):
        """
        Provide a list of all users who can access the document in the form of 
        """
        entries = []
        acl_feed = self._get_acl_feed()
        for acl_entry in acl_feed.entry:
            entries.append((acl_entry.scope.value, acl_entry.role.value))
        return entries

    def revision_history(self):
        """
        Get the revision history of the document from Google Docs.
        """
        for entry in self.docs_client.GetResources(limit=55).entry:
            revisions = self.docs_client.GetRevisions(entry)
            for revision in revisions.entry:
                print revision.publish, revision.GetPublishLink()
    
    def write(self, data_frame, header_rows=None, comment=None):
        """
        Write a pandas data frame to a google document. This function will overwrite existing cells, but will not clear them first.

        :param data_frame: the data frame to write.
        :type data_frame: pandas.DataFrame
        :param header_rows: number of header rows in the document.
        :type header_rows: int
        :param comment: a comment to make at the top of the document (requres header_rows>1
        :type comment: str
        """
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
        """
        Augment is a special wrapper function for update that calls it
        with overwrite set to False. Use this command if you only want
        to make changes when the cell in the spreadsheet is empty.
        """
        self.update(data_frame, columns, header_rows, comment, overwrite=False)


    def _get_feed(self, type, query=None, tries=0, max_tries=10):
        """
        Check for exceptions when calling for a group of cells from
        the google docs API. Retry a maximum number of times (default 10).
        """
        try:
            if type == 'cell':
                if query is None:
                    feed = self.gd_client.GetCellsFeed(self._key, wksht_id=self.worksheet_id)
                else:
                    feed = self.gd_client.GetCellsFeed(self._key, wksht_id=self.worksheet_id, query=query)
            elif type == 'list':
                feed = self.gd_client.GetListFeed(self._key, self.worksheet_id)
            elif type == 'worksheet':
                feed = self.gd_client.GetWorksheetsFeed(self._key)
            elif type == 'acl':
                feed = self.docs_client.GetAcl(self.document)
            elif type == 'resource':
                feed = self.docs_client.GetResourceById(self._key)
        except gdata.service.RequestError, inst:
            if tries<10:
                status = inst[0]['status']
                print "Error status: " + str(status) + '<br><br>' + inst[0]['reason'] + '<br><br>' + inst[0]['body']
                if status>499:
                    print "Try", tries, "of", max_tries, "waiting 2 seconds and retrying."
                    import time
                    time.sleep(2)
                    feed = self._get_feed(type=type, query=query, tries=tries+1)
                else:
                    raise 
            else:
                print "Max attempts at contacting Google exceeded."
                raise
        return feed

    def _get_cell_feed(self, query=None, tries=0, max_tries=10):
        """
        Wrapper for _get_feed() when a cell feed is required.
        """
        # problem: if there are only 1000 lines in the spreadsheet and you request more you get this error: 400 Invalid query parameter value for max-row.
        return self._get_feed(type='cell', query=query, tries=tries, max_tries=max_tries)

    def _get_resource_feed(self, tries=0, max_tries=10):
        """
        Wrapper for _get_feed() when a resource is required.
        """
        return self._get_feed(type='resource', tries=tries, max_tries=max_tries)

    def _get_list_feed(self, tries=0, max_tries=10):
        """
        Wrapper for _get_feed() when a list feed is required.
        """
        return self._get_feed(type='list', query=None, tries=tries, max_tries=max_tries)

    def _get_worksheet_feed(self, tries=0, max_tries=10):
        """
        Wrapper for _get_feed() when a cell worksheet feed is required.
        """
        return self._get_feed(type='worksheet', query=None, tries=tries, max_tries=max_tries)
    
    def _get_acl_feed(self, tries=0, max_tries=10):
        """
        Wrapper for _get_feed() when an acl feed is required.
        """
        return self._get_feed(type='acl', query=None, tries=tries, max_tries=max_tries)
    def update(self, data_frame, columns=None, header_rows=1, comment=None, overwrite=True):
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
        :type header_rows: int
        :param comment: comment to place in the top row of the header (requires header_rows>1)
        :type comment: str
        :rtype: pandas.DataFrame

        .. Note:: Returns the data frame that was found in the spreadsheet.

        """
        if not data_frame.index.is_unique:
            raise ValueError("Index for data_frame is not unique")
        ss = self.read(header_rows=header_rows)
        if not ss.index.is_unique:
            raise ValueError("Index in google doc is not unique")
        if columns is None:
            columns = ss.columns
        if (len(set(ss.columns) - set(data_frame.columns))>0 or
            len(set(data_frame.columns) - set(ss.columns))>0):
            # TODO: Have a lazy option that doesn't mind this mismatch and accounts for it.
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
                v = int(cells.entry[counter].cell.row)-header_rows
                row_to_delete.append(v)
                raise ValueError("Not willing to delete row indexed by " + current_index + " from " + cells.entry[counter].cell.row + " currently! Not comprehensively tested. Best guess is that row to delete is " + str(v))
                counter+=len(row)
                continue
            else:
                counter+=1
            for current_column, entry in row.iteritems():
                if (current_index, current_column) in update_cell:
                    val = data_frame[current_column][index]
                    if not pd.isnull(val):
                        v = []
                        try:
                            v = unicode(val)
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
        """
        Delete a row of the spreadsheet.
        :param row_number: the row number to be deleted.
        :type row_number: int"""
        list_feed = self._get_list_feed(self._key, self.worksheet_id)
        self.gd_client.DeleteRow(list_feed.entry[row_number])

    def _add_row(self, index, data_series):
        """
        Add a row to the spreadsheet.
        :param index: index of the row to be added.
        :type index: str or int (any valid index for a pandas.DataFrame)
        :param data_series: the entries of the row to be added.
        :type data_series: pandas.Series"""
        dict = {}
        dict['index'] = index
        for column, entry in data_series.iteritems():
            if not pd.isnull(entry):
                val = []
                try:
                    val = unicode(entry)
                except UnicodeDecodeError:
                    val = str(entry)
                dict[column] = val
        self.gd_client.InsertRow(dict, self._key, self.worksheet_id)


    def write_comment(self, comment, row=1, column=1):
        """Write a comment in the given cell"""
        query = gdata.spreadsheet.service.CellQuery()
        query.return_empty = "true" 
        query.min_col = str(column) 
        query.max_col = str(column)
        query.min_row = str(row)
        query.max_row = str(row)
        cells = self._get_cell_feed(query=query)
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
        cells = self._get_cell_feed(query=query)
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
                cells = self._get_cell_feed(query=query)
                batchRequest = gdata.spreadsheet.SpreadsheetsCellsFeed()
                counter = 0
            cells.entry[counter].cell.inputValue = str(index)
            batchRequest.AddUpdate(cells.entry[counter])
            counter+=1
            for entry in row:
                if not pd.isnull(entry):
                    val = []
                    try:
                        val = unicode(entry)
                    except UnicodeDecodeError:
                        val = str(entry)
                    cells.entry[counter].cell.inputValue = val
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

        cells = self._get_cell_feed(query=query)
        
        batchRequest = gdata.spreadsheet.SpreadsheetsCellsFeed()
        index_name = data_frame.index.name 
        if index_name == '' or index_name is None:
            index_name = 'index'
        headers = [index_name] + list(data_frame.columns)
        for i, column in enumerate(headers):
            cells.entry[i].cell.inputValue = column
            batchRequest.AddUpdate(cells.entry[i])

        return self.gd_client.ExecuteBatch(batchRequest, cells.GetBatchLink().href)

    def read(self, column_fields=None, header_rows=1, nan_values=[], read_values=False):
        """
        Read in information from a Google document storing entries. Fields present are defined in 'column_fields'
        
        :param column_fields: list of names to give to the columns (in case they aren't present in the spreadsheet). Default None (for None, the column headers are read from the spreadsheet.
        :type column_fields: list
        :param header_rows: number of rows to use as header (default is 1).
        :type header_rows: int
        :param nan_values: list containing entry types that are to be considered to be missing data (default is empty list).
        :type nan_values: list
        :param read_values: whether to read values rather than the formulae in the spreadsheet (default is False).
        :type read_values: bool
        """

        # todo: need to check if something is written below the 'table' as this will be read (for example a rogue entry in the row below the last row of the data.
        entries_dict = {}
        index_dict = {}
        cells =  self._get_cell_feed()
        read_column_fields = False
        if column_fields is None:
            read_column_fields = True
            column_fields = {}
        for myentry in cells.entry:
            col = myentry.cell.col
            row = myentry.cell.row
            if read_values:
                # Compute the evaluated cell entry
                value = myentry.cell.value
            else:
                # return a formula if it's present
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
