# Copyright 2014 Open Data Science Initiative and other authors. See AUTHORS.txt
# Licensed under the BSD 3-clause license (see LICENSE.txt)


import pandas as pd
import urlparse
import os
from config import *
import numpy as np

import pods.notebook as nb

gdata_available=True
try:
    import gdata.docs.client
    import gdata.spreadsheet.service 
except ImportError:
    gdata_available=False

if gdata_available:
    import atom

    class sheet():
        """
        Class for interchanging information between google spreadsheets and pandas data frames. The class manages a spreadsheet.

        :param spreadsheet_key: the google key of the spreadsheet to open (default is None which creates a new spreadsheet).
        :param worksheet_name: the worksheet in the spreadsheet to work with (default None which causes Sheet1 to be the name)
        :param title: the title of the spreadsheet (used if the spreadsheet is created for the first time)
        :param column_indent: the column indent to use in the spreadsheet.
        :type column_indent: int
        :param gd_client: the google spreadsheet service client to use (default is NOne which performs a programmatic login)
        :param docs_client: the google docs login client (default is none which causes a new client login)
        :param published: whether the google doc underlying the system has been published or not (default: False).
        :type published: bool
        """
        def __init__(self, spreadsheet_key=None, worksheet_name=None, title='Google Spreadsheet', column_indent=0, gd_client=None, docs_client=None, published=False):

            self.email = config.get('google docs', 'user')
            self.password = config.get('google docs', 'password')

            source = 'ODS Gdata Bot'                

            
            self.published = published

            if gd_client is None:
                self.gd_client = gdata.spreadsheet.service.SpreadsheetsService()
                self.gd_client.email = self.email
                self.gd_client.password = self.password
                self.gd_client.source = source
                self.gd_client.ProgrammaticLogin()
            else:
                self.gd_client=gd_client

            if docs_client is None:
                self.docs_client = gdata.docs.client.DocsClient()
                self.docs_client.client_login(self.email, self.password, source)
            else:
                self.docs_client = docs_client

            if spreadsheet_key is None:
                # need to create the document
                document = gdata.docs.data.Resource(type='spreadsheet', title=title)
                self.document = self.docs_client.create_resource(document)
                self._key = self.document.get_id().split("%3A")[1]
                # try to ensure that we can set title properly. Not sure why resource is not initially returned.
                self.document = self._get_resource_feed()
                self.feed = self._get_worksheet_feed()
                if worksheet_name is not None:
                    self.worksheet_name='Sheet1'
                    self.change_sheet_name(worksheet_name)

            else:
                # document exists already
                self._key = spreadsheet_key
                self.document = self._get_resource_feed()
                
            self.set_sheet_focus(worksheet_name=worksheet_name)

            self.column_indent = column_indent
            self.url = 'https://docs.google.com/spreadsheets/d/' + self._key + '/'


#############################################################################
# Place methods here that are really associated with individual worksheets. #
#############################################################################

        def change_sheet_name(self, title):
            """Change the title of the current worksheet to title."""
            for entry in self.feed.entry:
                if self.worksheet_name==entry.title.text:
                    entry.title=atom.Title(text=title)
                    self.gd_client.UpdateWorksheet(entry)
                    self.worksheet_name = title
                    return
            raise ValueError, "Can't find worksheet " + self.worksheet_name + " to change the name in Google spreadsheet " + self.url
                

        def set_sheet_focus(self, worksheet_name):
            """Set the current worksheet to the given name. If the name doesn't exist then create the sheet using sheet.add_sheet()"""
            self.update_sheet_list()
            # if the worksheet is set to None default to first sheet, warn if it's name is not "Sheet1".
            if worksheet_name is None:
                self.worksheet_name = self.feed.entry[0].title.text
                if len(self.feed.entry)>1 and self.worksheet_name != 'Sheet1':
                    print "Warning, multiple worksheets in this spreadsheet and no title specified. Assuming you are requesting the sheet called '{sheetname}'. To surpress this warning, please specify the sheet name.".format(sheetname=self.worksheet_name)
            else:
                if worksheet_name not in self.id_dict:
                    # create new worksheet here.
                    self.add_sheet(worksheet_name=worksheet_name)
                    self.worksheet_name = worksheet_name
                else:
                    self.worksheet_name = worksheet_name
            # Get list of ids from the spreadsheet
            self.worksheet_id = self.id_dict[self.worksheet_name]

        def add_sheet(self, worksheet_name, rows=100, columns=10):
            """Add a worksheet. To add and set to the current sheet use set_sheet_focus()."""
            self.gd_client.AddWorksheet(title=worksheet_name, row_count=rows, col_count=columns, key=self._key)
            self.update_sheet_list()

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
                    raise ValueError, 'Comment will be overwritten by column headers'
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
                raise ValueError, "Index for data_frame is not unique in Google spreadsheet " + self.url
            ss = self.read(header=header)
            if not ss.index.is_unique:
                raise ValueError, "Index in google doc is not unique in Google spreadsheet " + self.url
            if columns is None:
                columns = ss.columns
            if (len(set(ss.columns) - set(data_frame.columns))>0 or
                len(set(data_frame.columns) - set(ss.columns))>0):
                # TODO: Have a lazy option that doesn't mind this mismatch and accounts for it.
                raise ValueError, 'There is a mismatch between columns in online spreadsheet and the data frame we are using to update in Google spreadsheet ' + self.url
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
                    print "Warning deleting row indexed by '" + current_index + "' from " + cells.entry[counter].cell.row + " currently! Not comprehensively tested. Best guess is that row to delete is " + str(v) + " in Google spreadsheet " + self.url
                    ans = raw_input("Delete row (Y/N)?")
                    if len(ans)==0 or (not ans[0]=='Y' and not ans[0] == 'y'):
                        raise ValueError, "Not willing to delete row."
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
                print "Delete row ", row
                self._delete_row(row)
            # Insert the rows to be added
            for index in add_row:
                self._add_row(index, data_frame.loc[index])

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

        def write_body(self, data_frame, header):
            """Write the body of a data frame to a google doc."""
            # query needs to be set large enough to pull down relevant cells of sheet.
            row_number = header+1
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

        def write_headers(self, data_frame, header=1):
            """Write the headers of a data frame to the spreadsheet."""
            # query needs to be set large enough to pull down relevant cells of sheet.
            query = gdata.spreadsheet.service.CellQuery()
            query.return_empty = "true" 
            query.min_row = str(header)
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
            entries_dict = {}
            index_dict = {}
            cells =  self._get_cell_feed()
            read_names = False
            if names is None:
                read_names = True
                names = {}
            for myentry in cells.entry:
                col = myentry.cell.col
                row = myentry.cell.row
                if read_values:
                    # Compute the evaluated cell entry
                    value = myentry.cell.value
                else:
                    # return a formula if it's present
                    value = myentry.cell.inputValue
                if int(row)<header:
                    continue
                if int(row)==header:
                    if read_names:
                        # Read the column titles for the fields.
                        fieldname = value.strip()
                        if fieldname in names.values():
                            print "ValueError, Field name duplicated in header in sheet in ", self.worksheet_name, " in Google spreadsheet ", self.url
                            ans = raw_input('Try and fix the error on the sheet and then return here. Error fixed (Y/N)?')
                            if ans[0]=='Y' or ans[0] == 'y':
                                return self.read(names, header, na_values, read_values, dtype, usecols, index_field)
                            raise ValueError, "Field name duplicated in header in sheet in " + self.worksheet_name + " in Google spreadsheet " + self.url
                        else:
                            names[col] = fieldname
                    continue

                if not row in entries_dict:
                    entries_dict[row] = {}

                if col in names:
                    field = names[col]
                else:
                    field = col

                if ((index_field is None and field.lower() == 'index') 
                    or field==index_field):
                    val = value.strip()
                    if field in dtype:
                        index_dict[row] = dtype[field](val)
                    else:
                        index_dict[row] = val
                elif usecols is None or field in usecols:
                    val = value.strip()
                    if not val in na_values and val != '':
                        if field in dtype:
                            entries_dict[row][field] = dtype[field](val)
                        else:
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
                    try:
                        index.append(index_dict[key])
                    except KeyError:
                        print "KeyError, unidentified key in ", self.worksheet_name, " in Google spreadsheet ", self.url
                        ans = raw_input('Try and fix the error on the sheet and then return here. Error fixed (Y/N)?')
                        if ans[0]=='Y' or ans[0] == 'y':
                            return self.read(names, header, na_values, read_values, dtype, usecols, index_field)
                        else:
                            raise KeyError, "Unidentified key in " + self.worksheet_name + " in Google spreadsheet " + self.url

                else:
                    index.append(int(key)-header)

            if len(index)>0:
                entries = pd.DataFrame(entries, index=index)
            else:
                # this seems to cause problems, but it shouldn't come here now. If no index column is included index defaults to row number - header.
                entries = pd.DataFrame(entries)
            if len(names)>0:
                for field in names.values():
                    if field not in list(entries.columns) + ['index']:
                        if usecols is None or field in usecols:
                            entries[field] = np.NaN

                column_order = []
                for key in sorted(names, key=int):
                    if usecols is None or names[key] in usecols:
                        column_order.append(names[key])
                if 'index' in column_order:
                    column_order.remove('index')
                entries = entries[column_order]

            return entries

#######################################################################
# Place methods here that are really associated with the spreadsheet. #
#######################################################################

        def set_title(self, title):
            """Change the title of the google spreadsheet."""
            pass
            #self.document.title = atom.data.Title(text=title)
            #self.docs_client.update_resource(self.document)

        def get_title(self):
            """Get the title of the google spreadsheet."""
            return self.document.title.text

        def delete_sheet(self, worksheet_name):
            """Delete the worksheet with the given name."""
            if worksheet_name == self.worksheet_name:
                raise ValueError, "Can't delete the sheet I'm currently pointing to, use set_sheet_focus to change sheet first."
            for entry in self.feed.entry:
                if worksheet_name==entry.title.text:
                    self.gd_client.DeleteWorksheet(entry)
                    return
            raise ValueError, "Can't find worksheet " + worksheet_name + " to change the name " + " in Google spreadsheet " + self.url

        def update_sheet_list(self):
            """Update object with the worksheet feed and the list of worksheet_ids, can only be run once there is a spreadsheet key and a resource feed in place. Needs to be rerun if a worksheet is added."""
            self.feed = self._get_worksheet_feed()
            self.id_dict = self.worksheet_ids()

        def _repr_html_(self):
            if self.published: #self.document.published.tag=='published':
                url = self.url + '/pubhtml?widget=true&amp;headers=false' 
                return nb.iframe_url(url, width=500, height=300)
            else:
                output = '<p><b>Google Sheet</b> at <a href="{url}" target="_blank">this url.</a>\n</p>'.format(url=self.url)
                return output + self.read()._repr_html_()
                #return None
            

        def show(self, width=400, height=200):
            """If the IPython notebook is available, and the google
            spreadsheet is published, then the spreadsheet is displayed
            centrally in a box."""
            if self.published:
                try:
                    from IPython.display import HTML
                    url = self.url + '/pubhtml?widget=true&amp;headers=false' 
                    nb.iframe_url(url, width=width, height=height)
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
            raise ValueError, "User: " + str(user) + " not in the acl feed for this resource" + " in Google spreadsheet " + self.url


        def share_delete(self, user):
            """
            Remove sharing from a given user.
            """
            acl_entry = self._get_acl_entry(user)
            self.docs_client.DeleteAclEntry(acl_entry)

        def share_modify(self, user, share_type='reader', send_notifications=False):
            """
            :param user: email of the user to update.
            :type user: string
            :param share_type: type of sharing for the given user, type options are 'reader', 'writer', 'owner'
            :type user: string
            :param send_notifications: 
            """
            if share_type not in ['writer', 'reader', 'owner']:
                raise ValueError, "Share type should be 'writer', 'reader' or 'owner'"

            #acl_entry = self._get_acl_entry(user)# update ACL entry

            #acl_entry.role.value = share_type
            # According to Ali Afshar you need to remove the etag (https://groups.google.com/forum/#!msg/google-documents-list-api/eFSmo14nDLA/Oo4SjePHZd8J), can't work out how though!
            #etag_element = acl_entry.find('etag')
            #acl_entry.remove(etagelement)
            #self.docs_client.UpdateAclEntry(acl_entry, sent_notifications=send_notifications)
            # Hack: delete and re-add.
            self.share_delete(user)
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

            # Sometimes the server doesn't respond. Retry the request.
            except gdata.service.RequestError, inst:
                if tries<10:
                    status = inst[0]['status']
                    print "Error status: " + str(status) + '<br><br>' + inst[0]['reason'] + '<br><br>' + inst[0]['body']
                    if status>499:
                        print "Try", tries+1, "of", max_tries, "waiting 2 seconds and retrying."
                        import sys
                        sys.stdout.flush()
                        import time
                        time.sleep(2)
                        feed = self._get_feed(type=type, query=query, tries=tries+1)
                    else:
                        raise 
                else:
                    print "Maximum tries at contacting Google servers exceeded."
                    import sys
                    sys.stdout.flush()
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
