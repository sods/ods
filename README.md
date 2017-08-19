pods
===

# Python open data science software. 

This repository contains utilities and tools for open data science including tools for accessing data sets in python. 

This is very much an *alpha* release.

## Datasets

There is a set of notebooks describing the data sets that can be accessed available in the notebooks subdirectory. 

## Google Docs Interface

The google docs interface requires

```
pip install httplib2
pip install oauth2client
pip install google-api-python-client
pip install gspread
```

To access a spreadsheet from the script, you need to follow the
protocol for Oauth 2.0, the process is described (here)[https://developers.google.com/identity/protocols/OAuth2]

Once you have the key file, you can specify its location in the
`.ods_user.cfg` file, using for example

```
[google docs]
# Set the email address of an account to access google doc information.
oauth2_keyfile = $HOME/oauth2-key-file-name.json
```
If the `gdata` package is installed (`pip install gdata`) the library can be used as an interface between google spreadsheets and pandas.
