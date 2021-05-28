# Copyright 2014 Open Data Science Initiative and other authors. See AUTHORS.txt
# Licensed under the BSD 3-clause license (see LICENSE.txt)
from __future__ import print_function
from __future__ import absolute_import

import os
import sys
import csv
import copy
import numpy as np
import pylab as pb
import scipy.io
import datetime
import json
import yaml
import re

import logging

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s',
                    filename='/tmp/sods.log',
                    filemode='w')

from .util import download_url
from .config import *
from functools import reduce

ipython_available=True
try:
    import IPython
except ImportError:
    ipython_available=False

pandas_available=True
try:
    import pandas as pd
except ImportError:
    pandas_available=False

if sys.version_info>=(3,0):
    from urllib.parse import quote
    from urllib.request import urlopen
else:
    from urllib2 import quote
    from urllib2 import urlopen


# Global variables
data_path = os.path.expanduser(os.path.expandvars(config.get('datasets', 'dir')))
default_seed = 10000
overide_manual_authorize=False
ods_url = 'http://staffwww.dcs.shef.ac.uk/people/N.Lawrence/dataset_mirror/'

# Read data resources from json file.
# Don't do this when ReadTheDocs is scanning as it breaks things
on_rtd = os.environ.get('READTHEDOCS', None) == 'True' #Checks if RTD is scanning

if not (on_rtd):
    path = os.path.join(os.path.dirname(__file__), 'data_resources.json')
    from io import open as iopen
    json_data=iopen(path,encoding='utf-8').read()
    data_resources = json.loads(json_data)

if not (on_rtd):
    path = os.path.join(os.path.dirname(__file__), 'football_teams.json')
    from io import open as iopen
    json_data=iopen(path,encoding='utf-8').read()
    football_dict = json.loads(json_data, encoding='utf-8')


permute_data = True

# Some general utilities.
def permute(num):
    "Permutation for randomizing data order."
    if permute_data:
        return np.random.permutation(num)
    else:
        logging.warning("Warning not permuting data")
        return np.arange(num)

def integer(name):
    """Return a class category that forces integer"""
    return 'integer(' + name + ')'

def json_object(name='object'):
    """Returns a json object for general storage"""
    import json
    return 'jsonobject' + name + ''

def discrete(cats, name='discrete'):
    """Return a class category that shows the encoding"""
    import json
    ks = list(cats)
    for key in ks:
        if isinstance(key, bytes):
            cats[key.decode('utf-8')] = cats.pop(key)
    return 'discrete(' + json.dumps([cats, name]) + ')'

def datenum(name='date', format='%Y-%m-%d'):
    """Return a date category with format"""
    return 'datenum(' + name + ',' + format +')'

def timestamp(name='date', format='%Y-%m-%d'):
    """Return a date category with format"""
    return 'timestamp(' + name + ',' + format +')'

def datetime64_(name='date', format='%Y-%m-%d'):
    """Return a date category with format"""
    return 'datetime64(' + name + ',' + format +')'

def decimalyear(name='date', format='%Y-%m-%d'):
    """Return a date category with format"""
    return 'decimalyear(' + name + ',' + format +')'

def prompt_stdin(prompt):
    """Ask user for agreeing to data set licenses."""
    # raw_input returns the empty string for "enter"
    yes = set(['yes', 'y'])
    no = set(['no','n'])

    try:
        print(prompt)
        if sys.version_info>=(3,0):
            choice = input().lower()
        else:
            choice = raw_input().lower()
        # would like to test for which exceptions here
    except:
        print('Stdin is not implemented.')
        print('You need to set')
        print('overide_manual_authorize=True')
        print('to proceed with the download. Please set that variable and continue.')
        raise


    if choice in yes:
        return True
    elif choice in no:
        return False
    else:
        print("Your response was a " + choice)
        print("Please respond with 'yes', 'y' or 'no', 'n'")


def clear_cache(dataset_name=None):
    """Remove a data set from the cache"""
    dr = data_resources[dataset_name]
    if 'dirs' in dr:
        for dirs, files in zip(dr['dirs'], dr['files']):
            for dir, file in zip(dirs, files):
                path = os.path.join(data_path, dataset_name, dir, file)
                if os.path.exists(path):
                    logging.info("clear_cache: removing " + path)
                    os.unlink(path)
            for dir in dirs:
                path = os.path.join(data_path, dataset_name, dir)
                if os.path.exists(path):
                    logging.info("clear_cache: remove directory " + path)
                    os.rmdir(path)
        
    else:
        for file_list in dr['files']:
            for file in file_list:
                path = os.path.join(data_path, dataset_name, file)
                if os.path.exists(path):
                    logging.info("clear_cache: remove " + path)
                    os.unlink(path)
        
        
def data_available(dataset_name=None):
    """Check if the data set is available on the local machine already."""
    dr = data_resources[dataset_name]
    if 'dirs' in dr:
        for dirs, files in zip(dr['dirs'], dr['files']):
            for dir, file in zip(dirs, files):
                if not os.path.exists(os.path.join(data_path, dataset_name, dir, file)):
                    return False
    else:
        for file_list in dr['files']:
            for file in file_list:
                if not os.path.exists(os.path.join(data_path, dataset_name, file)):
                    return False
    return True


def authorize_download(dataset_name=None, prompt=prompt_stdin):
    """Check with the user that the are happy with terms and conditions for the data set."""
    print('Acquiring resource: ' + dataset_name)
    # TODO, check resource is in dictionary!
    print('')
    dr = data_resources[dataset_name]
    print('Details of data: ')
    print(dr['details'])
    print('')
    if dr['citation']:
        print('Please cite:')
        print(dr['citation'])
        print('')
    if dr['size']:
        print('After downloading the data will take up ' + str(dr['size']) + ' bytes of space.')
        print('')
    print('Data will be stored in ' + os.path.join(data_path, dataset_name) + '.')
    print('')
    if overide_manual_authorize:
        if dr['license']:
            print('You have agreed to the following license:')
            print(dr['license'])
            print('')
        return True
    else:
        if dr['license']:
            print('You must also agree to the following license:')
            print(dr['license'])
            print('')
        return prompt('Do you wish to proceed with the download? [yes/no]')


def download_data(dataset_name=None, prompt=prompt_stdin):
    """Check with the user that the are happy with terms and conditions for the data set, then download it."""
        
    dr = data_resources[dataset_name]
    if not authorize_download(dataset_name, prompt=prompt):
        raise Exception("Permission to download data set denied.")
    
    if 'suffices' in dr:
        for url, files, suffices in zip(dr['urls'], dr['files'], dr['suffices']):
            for file, suffix in zip(files, suffices):
                download_url(url=os.path.join(url,file),
                             dir_name = data_path,
                             store_directory=dataset_name,
                             suffix=suffix)
    elif 'dirs' in dr:
        for url, dirs, files in zip(dr['urls'], dr['dirs'], dr['files']):
            for file, dir in zip(files, dirs):
                print(file, dir)
                download_url(
                    url=os.path.join(url,dir,file),
                    dir_name = data_path,
                    store_directory=os.path.join(dataset_name,dir)
                    )
    else:
        for url, files in zip(dr['urls'], dr['files']):
            for file in files:
                download_url(
                    url=os.path.join(url,file),
                    dir_name = data_path,
                    store_directory=dataset_name
                    )
    return True

def data_details_return(data, data_set):
    """Update the data component of the data dictionary with details drawn from the data_resources."""
    data.update(data_resources[data_set])
    return data


def df2arff(df, dataset_name, pods_data):
    """Write an arff file from a data set loaded in from pods"""
    def java_simple_date(date_format):
        date_format = date_format.replace('%Y', 'yyyy').replace('%m', 'MM').replace('%d', 'dd').replace('%H', 'HH')
        return date_format.replace('%h', 'hh').replace('%M', 'mm').replace('%S', 'ss').replace('%f', 'SSSSSS')
    
    def tidy_field(atr):
        return str(atr).replace(' / ', '/').replace(' ', '_')
    types = {'STRING': [str], 'INTEGER': [int, np.int64, np.uint8], 'REAL': [np.float64]}
    d = {}
    d['attributes'] = []
    for atr in df.columns:
        if isinstance(atr, str):
            if len(atr)>8 and atr[:9] == 'discrete(':
                import json
                elements = json.loads(atr[9:-1])
                d['attributes'].append((tidy_field(elements[1]),
                                         list(elements[0].keys())))
                mask = {}
                c = pd.Series(index=df.index)
                for key, val in elements[0].items():
                    mask = df[atr]==val
                    c[mask] = key
                df[atr] = c
                continue
            if len(atr)>7 and atr[:8] == 'integer(':
                name = atr[8:-1]
                d['attributes'].append((tidy_field(name), 'INTEGER'))
                df[atr] = df[atr].astype(int)
                continue
            if len(atr)>7 and atr[:8]=='datenum(':
                from matplotlib.dates import num2date
                elements = atr[8:-1].split(',')
                d['attributes'].append((elements[0] + '_datenum_' + java_simple_date(elements[1]), 'STRING'))
                df[atr] = num2date(df[atr].values) #
                df[atr] = df[atr].dt.strftime(elements[1])
                continue
            if len(atr)>9 and atr[:10]=='timestamp(':
                def timestamp2date(values):
                    import datetime
                    """Convert timestamp into a date object"""
                    new = []
                    for value in values:
                        new.append(np.datetime64(datetime.datetime.fromtimestamp(value)))
                    return np.asarray(new)
                elements = atr[10:-1].split(',')
                d['attributes'].append((elements[0] + '_datenum_' + java_simple_date(elements[1]), 'STRING'))
                df[atr] = timestamp2date(df[atr].values) #
                df[atr] = df[atr].dt.strftime(elements[1])
                continue
            if len(atr)>10 and atr[:11]=='datetime64(':
                elements = atr[11:-1].split(',')
                d['attributes'].append((elements[0] + '_datenum_' + java_simple_date(elements[1]), 'STRING'))
                df[atr] = df[atr].dt.strftime(elements[1])
                continue
            if len(atr)>11 and atr[:12]=='decimalyear(':
                def decyear2date(values):
                    """Convert decimal year into a date object"""
                    new = []
                    for i, decyear in enumerate(values):
                        year = int(np.floor(decyear))
                        dec = decyear-year
                        end = np.datetime64(str(year+1)+'-01-01')
                        start = np.datetime64(str(year)+'-01-01')
                        diff=end-start
                        days = dec*(diff/np.timedelta64(1, 'D'))
                        # round to nearest day
                        add = np.timedelta64(int(np.round(days)), 'D')
                        new.append(start+add)
                    return np.asarray(new)
                elements = atr[12:-1].split(',')
                d['attributes'].append((elements[0] + '_datenum_' + java_simple_date(elements[1]), 'STRING'))
                df[atr] = decyear2date(df[atr].values) #
                df[atr] = df[atr].dt.strftime(elements[1])
                continue

        field = tidy_field(atr)
        el = df[atr][0]
        type_assigned=False
        for t in types:
            if isinstance(el, tuple(types[t])):
                d['attributes'].append((field, t))
                type_assigned=True
                break
        if not type_assigned:
            import json
            d['attributes'].append((field+'_json', 'STRING'))
            df[atr] = df[atr].apply(json.dumps)

    d['data'] = []
    for ind, row in df.iterrows():
        d['data'].append(list(row))

    import textwrap as tw
    width = 78
    d['description'] = dataset_name + "\n\n"
    if 'info' in pods_data and pods_data['info']:
        d['description'] += "\n".join(tw.wrap(pods_data['info'], width)) + "\n\n"
    if 'details' in pods_data and pods_data['details']:
        d['description'] += "\n".join(tw.wrap(pods_data['details'], width))
    if 'citation' in pods_data and pods_data['citation']:
        d['description'] += "\n\n" + "Citation" "\n\n" + "\n".join(tw.wrap(pods_data['citation'], width))

    d['relation'] = dataset_name
    import arff
    string = arff.dumps(d)
    import re
    string = re.sub(r'\@ATTRIBUTE "?(.*)_datenum_(.*)"? STRING',
                    r'@ATTRIBUTE "\1" DATE [\2]',
                    string)
    f = open(dataset_name + '.arff', 'w')
    f.write(string)
    f.close()

def to_arff(dataset, **kwargs):
    """Take a pods data set and write it as an ARFF file"""
    pods_data = dataset(**kwargs)
    vals = list(kwargs.values())
    for i, v in enumerate(vals):
        if isinstance(v, list):
            vals[i] = '|'.join(v)
        else:
            vals[i] = str(v)
    args = '_'.join(vals)
    n = dataset.__name__
    if len(args)>0:
        n += '_' + args
        n = n.replace(' ', '-')
    ks = pods_data.keys()
    d = None
    if 'Y' in ks and 'X' in ks: 
        d = pd.DataFrame(pods_data['X'])
        if 'Xtest' in ks:
            d = d.append(pd.DataFrame(pods_data['Xtest']), ignore_index=True)
        if 'covariates' in ks:
            d.columns = pods_data['covariates']
        dy = pd.DataFrame(pods_data['Y'])
        if 'Ytest' in ks:
            dy = dy.append(pd.DataFrame(pods_data['Ytest']), ignore_index=True)
        if 'response' in ks:
            dy.columns = pods_data['response']
        for c in dy.columns:
            if c not in d.columns:
                d[c] = dy[c]
            else:
                d['y'+str(c)] = dy[c]
    elif 'Y' in ks:
        d = pd.DataFrame(pods_data['Y'])
        if 'Ytest' in ks:
            d = d.append(pd.DataFrame(pods_data['Ytest']), ignore_index=True)

    elif 'data' in ks:
        d = pd.DataFrame(pods_data['data'])
    if d is not None:
        df2arff(d, n, pods_data)


def cmu_urls_files(subj_motions, messages = True):
    """
    Find which resources are missing on the local disk for the requested CMU motion capture motions.

    :param subj_motions: the subject motions to be checked for.
    :type subj_motions: tuple of lists containing subject numbers and motion numbers.
    """
    dr = data_resources['cmu_mocap_full']
    cmu_url = dr['urls'][0]

    subjects_num = subj_motions[0]
    motions_num = subj_motions[1]

    resource = {'urls' : [], 'files' : []}
    # Convert numbers to strings
    subjects = []
    motions = [list() for _ in range(len(subjects_num))]
    for i in range(len(subjects_num)):
        curSubj = str(int(subjects_num[i]))
        if int(subjects_num[i]) < 10:
            curSubj = '0' + curSubj
        subjects.append(curSubj)
        for j in range(len(motions_num[i])):
            curMot = str(int(motions_num[i][j]))
            if int(motions_num[i][j]) < 10:
                curMot = '0' + curMot
            motions[i].append(curMot)

    all_skels = []

    assert len(subjects) == len(motions)

    all_motions = []

    for i in range(len(subjects)):
        skel_dir = os.path.join(data_path, 'cmu_mocap')
        cur_skel_file = os.path.join(skel_dir, subjects[i] + '.asf')

        url_required = False
        file_download = []
        if not os.path.exists(cur_skel_file):
            # Current skel file doesn't exist.
            if not os.path.isdir(skel_dir):
                os.makedirs(skel_dir)
            # Add skel file to list.
            url_required = True
            file_download.append(subjects[i] + '.asf')
        for j in range(len(motions[i])):
            file_name = subjects[i] + '_' + motions[i][j] + '.amc'
            cur_motion_file = os.path.join(skel_dir, file_name)
            if not os.path.exists(cur_motion_file):
                url_required = True
                file_download.append(subjects[i] + '_' + motions[i][j] + '.amc')
        if url_required:
            resource['urls'].append(cmu_url + '/' + subjects[i] + '/')
            resource['files'].append(file_download)
    return resource


# The data sets
def boston_housing(data_set='boston_housing'):
    if not data_available(data_set):
        download_data(data_set)
    all_data = np.genfromtxt(os.path.join(data_path, data_set, 'housing.data'))
    X = all_data[:, 0:13]
    Y = all_data[:, 13:14]
    return data_details_return({'X' : X, 'Y': Y}, data_set)



def boxjenkins_airline(data_set='boxjenkins_airline', num_train=96):
    path = os.path.join(data_path, data_set)
    if not data_available(data_set):
        download_data(data_set)
    data = np.loadtxt(os.path.join(data_path, data_set, 'boxjenkins_airline.csv'), delimiter=',')
    Y = data[:num_train, 1:2]
    X = data[:num_train, 0:1]
    Xtest = data[num_train:, 0:1]
    Ytest = data[num_train:, 1:2]

    return data_details_return({'X': X, 'Y': Y, 'Xtest': Xtest, 'Ytest': Ytest, 'covariates' : [decimalyear('year')], 'response' : ['AirPassengers'], 'info': "Monthly airline passenger data from Box & Jenkins 1976."}, data_set)

def brendan_faces(data_set='brendan_faces'):
    if not data_available(data_set):
        download_data(data_set)
    mat_data = scipy.io.loadmat(os.path.join(data_path, data_set, 'frey_rawface.mat'))
    Y = mat_data['ff'].T
    return data_details_return({'Y': Y}, data_set)

def della_gatta_TRP63_gene_expression(data_set='della_gatta', gene_number=None):
    if not data_available(data_set):
        download_data(data_set)
    mat_data = scipy.io.loadmat(os.path.join(data_path, data_set, 'DellaGattadata.mat'))
    X = np.double(mat_data['timepoints'])
    if gene_number == None:
        Y = mat_data['exprs_tp53_RMA']
    else:
        Y = mat_data['exprs_tp53_RMA'][:, gene_number]
        if len(Y.shape) == 1:
            Y = Y[:, None]
    return data_details_return({'X': X, 'Y': Y, 'gene_number' : gene_number}, data_set)


def epomeo_gpx(data_set='epomeo_gpx', sample_every=4):
    """Data set of three GPS traces of the same movement on Mt Epomeo in Ischia. Requires gpxpy to run."""
    import gpxpy
    import gpxpy.gpx
    if not data_available(data_set):
        download_data(data_set)
    files = ['endomondo_1', 'endomondo_2', 'garmin_watch_via_endomondo','viewranger_phone', 'viewranger_tablet']

    X = []
    for file in files:
        gpx_file = open(os.path.join(data_path, 'epomeo_gpx', file + '.gpx'), 'r')

        gpx = gpxpy.parse(gpx_file)
        segment = gpx.tracks[0].segments[0]
        points = [point for track in gpx.tracks for segment in track.segments for point in segment.points]
        data = [[(point.time-datetime.datetime(2013,8,21)).total_seconds(), point.latitude, point.longitude, point.elevation] for point in points]
        X.append(np.asarray(data)[::sample_every, :])
        gpx_file.close()
    if pandas_available:
        X = pd.DataFrame(X[0], columns=['seconds', 'latitude', 'longitude', 'elevation'])
        X.set_index(keys='seconds', inplace=True)
    return data_details_return({'X' : X, 'info' : 'Data is an array containing time in seconds, latitude, longitude and elevation in that order.'}, data_set)

def nigerian_administrative_zones(data_set='nigerian_administrative_zones', refresh_data=False):
    if not data_available(data_set) and not refresh_data:
        download_data(data_set)
    from zipfile import ZipFile
    with ZipFile(os.path.join(data_path, data_set, 'nga_admbnda_osgof_eha_itos.gdb.zip'), 'r') as zip_ref:
        zip_ref.extractall(os.path.join(data_path, data_set, 'nga_admbnda_osgof_eha_itos.gdb'))
    states_file = "nga_admbnda_osgof_eha_itos.gdb/nga_admbnda_osgof_eha_itos.gdb/nga_admbnda_osgof_eha_itos.gdb/nga_admbnda_osgof_eha_itos.gdb/"
    from geopandas import read_file
    Y = read_file(os.path.join(data_path, data_set, states_file), layer=1)
    Y.crs = "EPSG:4326"
    Y.set_index('admin1Name_en')
    return data_details_return({'Y': Y}, data_set)
    
def nigerian_covid(data_set='nigerian_covid', refresh_data=False):
    if not data_available(data_set) and not refresh_data:
        download_data(data_set)
    from pandas import read_csv
    dir_path = os.path.join(data_path, data_set)
    filename = os.path.join(dir_path, 'line-list-nigeria.csv')
    Y = read_csv(filename, parse_dates=['date',
                                        'date_confirmation',
                                        'date_onset_symptoms',
                                        'date_admission_hospital',
                                        'death_date'])
    return data_details_return({'Y': Y}, data_set)

def nigerian_nmis(data_set='nigerian_nmis', refresh_data=False):
    if not data_available(data_set) and not refresh_data:
        download_data(data_set)
    from pandas import read_csv
    dir_path = os.path.join(data_path, data_set)
    filename = os.path.join(dir_path, 'healthmopupandbaselinenmisfacility.csv')
    Y = read_csv(filename)
    return data_details_return({'Y': Y}, data_set)


def nigerian_population_2016(data_set='nigerian_population_2016', refresh_data=False):
    if not data_available(data_set) and not refresh_data:
        download_data(data_set)
    from pandas import read_csv
    dir_path = os.path.join(data_path, data_set)
    filename = os.path.join(dir_path, 'nga_pop_adm1_2016.csv')
    Y = read_csv(filename)
    Y.columns = ['admin1Name_en', 'admin1Pcode', 'admin0Name_en', 'admin0Pcode', 'population']
    Y = Y.set_index('admin1Name_en')
    return data_details_return({'Y': Y}, data_set)


def pmlr(volumes='all', data_set='pmlr', refresh_data=False):
    """Abstracts from the Proceedings of Machine Learning Research"""
    if not data_available(data_set) and not refresh_data:
        download_data(data_set)
        
    proceedings_file = open(os.path.join(data_path, data_set, 'proceedings.yaml'), 'r')
    import yaml
    proceedings = yaml.load(proceedings_file, Loader=yaml.FullLoader)
    
    # Create a new resources entry for downloading contents of proceedings.
    data_name_full_stub = 'pmlr_volume_'
    for entry in proceedings:
        data_name_full = data_name_full_stub + 'v' + str(entry['volume'])
        data_resources[data_name_full] = data_resources[data_set].copy()
        data_resources[data_name_full]['files'] = []
        data_resources[data_name_full]['dirs'] = []
        data_resources[data_name_full]['urls'] = []
        if volumes=='all' or entry['volume'] in volumes:
            file = entry['yaml'].split('/')[-1]
            proto, url = entry['yaml'].split('//')
            file = os.path.basename(url)
            dirname = os.path.dirname('/'.join(url.split('/')[1:]))
            urln = proto + '//' + url.split('/')[0]
            data_resources[data_name_full]['files'].append([file])
            data_resources[data_name_full]['dirs'].append([dirname])
            data_resources[data_name_full]['urls'].append(urln)
        Y = []
        # Download the volume data
        if not data_available(data_name_full):
            download_data(data_name_full)
            
    for entry in reversed(proceedings):
        volume =  entry['volume']
        data_name_full = data_name_full_stub + 'v' + str(volume)
        if volumes == 'all' or volume in volumes:
            file = entry['yaml'].split('/')[-1]
            proto, url = entry['yaml'].split('//')
            file = os.path.basename(url)
            dirname = os.path.dirname('/'.join(url.split('/')[1:]))
            urln = proto + '//' + url.split('/')[0]
            volume_file = open(os.path.join(data_path,
                                            data_name_full,
                                            dirname,
                                            file), 'r')
            Y+=yaml.load(volume_file, Loader=yaml.FullLoader)
    if pandas_available:
        Y = pd.DataFrame(Y)
        Y['published'] = pd.to_datetime(Y['published'])
        #Y.columns.values[4] = json_object('authors')
        #Y.columns.values[7] = json_object('editors')
        Y['issued'] = Y['issued'].apply(lambda x: np.datetime64(datetime.datetime(*x['date-parts'])))
        Y['author'] = Y['author'].apply(lambda x: [str(author['given']) + ' ' + str(author['family']) for author in x])
        Y['editor'] = Y['editor'].apply(lambda x: [str(editor['given']) + ' ' + str(editor['family']) for editor in x])
        columns = list(Y.columns)
        columns[14] = datetime64_('published')
        columns[11] = datetime64_('issued')
        Y.columns = columns
        
    return data_details_return({'Y' : Y, 'info' : 'Data is a pandas data frame containing each paper, its abstract, authors, volumes and venue.'}, data_set)
   
        
def football_data(season='1617', data_set='football_data'):
    """Football data from English games since 1993. This downloads data from football-data.co.uk for the given season. """
    league_dict = {'E0':0, 'E1':1, 'E2': 2, 'E3': 3, 'EC':4}
    def league2num(string):
        if isinstance(string, bytes):
            string = string.decode('utf-8')
        return league_dict[string]

    def football2num(string):
        if isinstance(string, bytes):
            string = string.decode('utf-8')
        if string in football_dict:
            return football_dict[string]
        else:
            football_dict[string] = len(football_dict)+1
            return len(football_dict)+1

    def datestr2num(s):
        import datetime
        from matplotlib.dates import date2num
        return date2num(datetime.datetime.strptime(s.decode('utf-8'),'%d/%m/%y'))
    data_set_season = data_set + '_' + season
    data_resources[data_set_season] = copy.deepcopy(data_resources[data_set])
    data_resources[data_set_season]['urls'][0]+=season + '/'
    start_year = int(season[0:2])
    end_year = int(season[2:4])
    files = ['E0.csv', 'E1.csv', 'E2.csv', 'E3.csv']
    if start_year>4 and start_year < 93:
        files += ['EC.csv']
    data_resources[data_set_season]['files'] = [files]
    if not data_available(data_set_season):
        download_data(data_set_season)
    start = True
    for file in reversed(files):
        filename = os.path.join(data_path, data_set_season, file)
        # rewrite files removing blank rows.
        writename = os.path.join(data_path, data_set_season, 'temp.csv')
        input = open(filename, encoding='ISO-8859-1')
        output = open(writename, 'w')
        writer = csv.writer(output)
        for row in csv.reader(input):
            if any(field.strip() for field in row):
                writer.writerow(row)
        input.close()
        output.close()
        table = np.loadtxt(writename,skiprows=1, usecols=(0, 1, 2, 3, 4, 5), converters = {0: league2num, 1: datestr2num, 2:football2num, 3:football2num}, delimiter=',')
        if start:
            X = table[:, :4]
            Y = table[:, 4:]
            start=False
        else:
            X = np.append(X, table[:, :4], axis=0)
            Y = np.append(Y, table[:, 4:], axis=0)
    return data_details_return({'X': X, 'Y': Y, 'covariates': [discrete(league_dict, 'league'), datenum('match_day'), discrete(football_dict, 'home team'), discrete(football_dict, 'away team')], 'response': [integer('home score'), integer('away score')]}, data_set)

def sod1_mouse(data_set='sod1_mouse'):
    if not data_available(data_set):
        download_data(data_set)
    from pandas import read_csv
    dir_path = os.path.join(data_path, data_set)
    filename = os.path.join(dir_path, 'sod1_C57_129_exprs.csv')
    Y = read_csv(filename, header=0, index_col=0)
    num_repeats=4
    num_time=4
    num_cond=4
    return data_details_return({'Y': Y}, data_set)

def spellman_yeast(data_set='spellman_yeast'):
    """This is the classic Spellman et al 1998 Yeast Cell Cycle gene expression data that is widely used as a benchmark."""
    if not data_available(data_set):
        download_data(data_set)
    from pandas import read_csv
    dir_path = os.path.join(data_path, data_set)
    filename = os.path.join(dir_path, 'combined.txt')
    Y = read_csv(filename, header=0, index_col=0, sep='\t')
    return data_details_return({'Y': Y}, data_set)

def spellman_yeast_cdc15(data_set='spellman_yeast'):
    """These are the gene expression levels from the CDC-15 experiment of Spellman et al (1998)."""
    if not data_available(data_set):
        download_data(data_set)
    from pandas import read_csv
    dir_path = os.path.join(data_path, data_set)
    filename = os.path.join(dir_path, 'combined.txt')
    Y = read_csv(filename, header=0, index_col=0, sep='\t')
    t = np.asarray([10, 30, 50, 70, 80, 90, 100, 110, 120, 130, 140, 150, 170, 180, 190, 200, 210, 220, 230, 240, 250, 270, 290])
    times = ['cdc15_'+str(time) for time in t]
    Y = Y[times].T
    t = t[:, None]
    return data_details_return({'Y' : Y, 't': t, 'info': 'Time series of synchronized yeast cells from the CDC-15 experiment of Spellman et al (1998).'}, data_set)

def lee_yeast_ChIP(data_set='lee_yeast_ChIP'):
    """Yeast ChIP data from Lee et al."""
    if not data_available(data_set):
        download_data(data_set)
    from pandas import read_csv
    dir_path = os.path.join(data_path, data_set)
    filename = os.path.join(dir_path, 'binding_by_gene.tsv')
    S = read_csv(filename, header=1, index_col=0, sep='\t')
    transcription_factors = [col for col in S.columns if col[:7] != 'Unnamed']
    annotations = S[['Unnamed: 1', 'Unnamed: 2', 'Unnamed: 3']]
    S = S[transcription_factors]
    return data_details_return({'annotations' : annotations, 'Y' : S, 'transcription_factors': transcription_factors}, data_set)



def fruitfly_tomancak(data_set='fruitfly_tomancak', gene_number=None):
    """Fruitfly gene expression data from Tomancak et al."""
    if not data_available(data_set):
        download_data(data_set)
    from pandas import read_csv
    dir_path = os.path.join(data_path, data_set)
    filename = os.path.join(dir_path, 'tomancak_exprs.csv')
    Y = read_csv(filename, header=0, index_col=0).T
    num_repeats = 3
    num_time = 12
    xt = np.linspace(0, num_time-1, num_time)
    xr = np.linspace(0, num_repeats-1, num_repeats)
    xtime, xrepeat = np.meshgrid(xt, xr)
    X = np.vstack((xtime.flatten(), xrepeat.flatten())).T
    return data_details_return({'X': X, 'Y': Y, 'gene_number' : gene_number}, data_set)

def drosophila_protein(data_set='drosophila_protein'):
    if not data_available(data_set):
        download_data(data_set)
    from pandas import read_csv
    dir_path = os.path.join(data_path, data_set)
    filename = os.path.join(dir_path, 'becker_et_al.csv')
    Y = read_csv(filename, header=0)
    return data_details_return({'Y': Y}, data_set)

def drosophila_knirps(data_set='drosophila_protein'):
    if not data_available(data_set):
        download_data(data_set)
    from pandas import read_csv
    dir_path = os.path.join(data_path, data_set)
    filename = os.path.join(dir_path, 'becker_et_al.csv')
    # in the csv file we have facts_kni and ext_kni. We treat facts_kni as protein and ext_kni as mRNA
    df = read_csv(filename, header=0)
    t = df['t'][:,None]
    x = df['x'][:,None]

    g = df['expression1'][:,None]
    p = df['expression2'][:,None]

    leng = x.shape[0]

    T = np.vstack([t,t])
    S = np.vstack([x,x])
    inx = np.zeros(leng*2)[:,None]

    inx[leng*2//2:leng*2]=1
    X = np.hstack([T,S,inx])
    Y = np.vstack([g,p])
    return data_details_return({'Y': Y, 'X': X}, data_set)

# This will be for downloading google trends data.
def google_trends(query_terms=['big data', 'machine learning', 'data science'], data_set='google_trends', refresh_data=False):
    """
    Data downloaded from Google trends for given query terms. Warning,
    if you use this function multiple times in a row you get blocked
    due to terms of service violations.

    The function will cache the result of any query in an attempt to
    avoid this. If you wish to refresh an old query set refresh_data
    to True. The function is inspired by this notebook:

    http://nbviewer.ipython.org/github/sahuguet/notebooks/blob/master/GoogleTrends%20meet%20Notebook.ipynb

    """

    query_terms.sort()
    import pandas as pd

    # Create directory name for data
    dir_path = os.path.join(data_path,'google_trends')
    if not os.path.isdir(dir_path):
        os.makedirs(dir_path)
    dir_name = '-'.join(query_terms)
    dir_name = dir_name.replace(' ', '_')
    dir_path = os.path.join(dir_path,dir_name)
    file = 'data.csv'
    file_name = os.path.join(dir_path,file)
    if not os.path.exists(file_name) or refresh_data:
        print("Accessing Google trends to acquire the data. Note that repeated accesses will result in a block due to a google terms of service violation. Failure at this point may be due to such blocks.")
        # quote the query terms.
        quoted_terms = []
        for term in query_terms:
            quoted_terms.append(quote(term))
        print("Query terms: ", ', '.join(query_terms))

        print("Fetching query:")
        query = 'http://www.google.com/trends/fetchComponent?q=%s&cid=TIMESERIES_GRAPH_0&export=3' % ",".join(quoted_terms)

        data = urlopen(query).read().decode('utf8')
        print("Done.")
        # In the notebook they did some data cleaning: remove Javascript header+footer, and translate new Date(....,..,..) into YYYY-MM-DD.
        header = """// Data table response\ngoogle.visualization.Query.setResponse("""
        data = data[len(header):-2]
        data = re.sub('new Date\((\d+),(\d+),(\d+)\)', (lambda m: '"%s-%02d-%02d"' % (m.group(1).strip(), 1+int(m.group(2)), int(m.group(3)))), data)
        timeseries = json.loads(data)
        columns = [k['label'] for k in timeseries['table']['cols']]
        rows = list(map(lambda x: [k['v'] for k in x['c']], timeseries['table']['rows']))
        df = pd.DataFrame(rows, columns=columns)
        if not os.path.isdir(dir_path):
            os.makedirs(dir_path)

        df.to_csv(file_name)
    else:
        print("Reading cached data for google trends. To refresh the cache set 'refresh_data=True' when calling this function.")
        print("Query terms: ", ', '.join(query_terms))

        df = pd.read_csv(file_name, parse_dates=[0])

    columns = df.columns
    terms = len(query_terms)
    import datetime
    from matplotlib.dates import date2num
    X = np.asarray([(date2num(datetime.datetime.strptime(df.ix[row]['Date'], '%Y-%m-%d')), i) for i in range(terms) for row in df.index])
    Y = np.asarray([[df.ix[row][query_terms[i]]] for i in range(terms) for row in df.index ])
    output_info = columns[1:]
    cats = {}
    for i in range(terms):
        cats[query_terms[i]] = i
    return data_details_return({'data frame' : df, 'X': X, 'Y': Y, 'query_terms': query_terms, 'info': "Data downloaded from google trends with query terms: " + ', '.join(query_terms) + '.', 'covariates' : [datenum('date'), discrete(cats, 'query_terms')], 'response' : ['normalized interest']}, data_set)


def oil(data_set='three_phase_oil_flow'):
    """The three phase oil data from Bishop and James (1993)."""
    if not data_available(data_set):
        download_data(data_set)
    oil_train_file = os.path.join(data_path, data_set, 'DataTrn.txt')
    oil_trainlbls_file = os.path.join(data_path, data_set, 'DataTrnLbls.txt')
    oil_test_file = os.path.join(data_path, data_set, 'DataTst.txt')
    oil_testlbls_file = os.path.join(data_path, data_set, 'DataTstLbls.txt')
    oil_valid_file = os.path.join(data_path, data_set, 'DataVdn.txt')
    oil_validlbls_file = os.path.join(data_path, data_set, 'DataVdnLbls.txt')
    fid = open(oil_train_file)
    X = np.fromfile(fid, sep='\t').reshape((-1, 12))
    fid.close()
    fid = open(oil_test_file)
    Xtest = np.fromfile(fid, sep='\t').reshape((-1, 12))
    fid.close()
    fid = open(oil_valid_file)
    Xvalid = np.fromfile(fid, sep='\t').reshape((-1, 12))
    fid.close()
    fid = open(oil_trainlbls_file)
    Y = np.fromfile(fid, sep='\t').reshape((-1, 3)) * 2. - 1.
    fid.close()
    fid = open(oil_testlbls_file)
    Ytest = np.fromfile(fid, sep='\t').reshape((-1, 3)) * 2. - 1.
    fid.close()
    fid = open(oil_validlbls_file)
    Yvalid = np.fromfile(fid, sep='\t').reshape((-1, 3)) * 2. - 1.
    fid.close()
    return data_details_return({'X': X, 'Y': Y, 'Xtest': Xtest, 'Ytest': Ytest, 'Xtest' : Xtest, 'Xvalid': Xvalid, 'Yvalid': Yvalid}, data_set)
    #else:
    # throw an error

def leukemia(data_set='leukemia'):
    if not data_available(data_set):
        download_data(data_set)
    all_data = np.genfromtxt(os.path.join(data_path, data_set, 'leuk.dat'))
    X = all_data[1:, 1:]
    censoring = all_data[1:, 1]
    Y = all_data[1:, 0]
    return data_details_return({'X' : X, 'censoring': censoring, 'Y': Y}, data_set)

def oil_100(seed=default_seed, data_set = 'three_phase_oil_flow'):
    np.random.seed(seed=seed)
    data = oil()
    indices = permute(1000)
    indices = indices[0:100]
    X = data['X'][indices, :]
    Y = data['Y'][indices, :]
    return data_details_return({'X': X, 'Y': Y, 'info': "Subsample of the full oil data extracting 100 values randomly without replacement, here seed was " + str(seed)}, data_set)

def pumadyn(seed=default_seed, data_set='pumadyn-32nm'):
    """Data from a simulation of the Puma robotic arm generated by Zoubin Ghahramani."""
    if not data_available(data_set):
        import tarfile
        download_data(data_set)
        path = os.path.join(data_path, data_set)
        tar = tarfile.open(os.path.join(path, 'pumadyn-32nm.tar.gz'))
        print('Extracting file.')
        tar.extractall(path=path)
        tar.close()
    # Data is variance 1, no need to normalize.
    data = np.loadtxt(os.path.join(data_path, data_set, 'pumadyn-32nm', 'Dataset.data.gz'))
    indices = permute(data.shape[0])
    indicesTrain = indices[0:7168]
    indicesTest = indices[7168:-1]
    indicesTrain.sort(axis=0)
    indicesTest.sort(axis=0)
    X = data[indicesTrain, 0:-2]
    Y = data[indicesTrain, -1][:, None]
    Xtest = data[indicesTest, 0:-2]
    Ytest = data[indicesTest, -1][:, None]
    return data_details_return({'X': X, 'Y': Y, 'Xtest': Xtest, 'Ytest': Ytest, 'seed': seed}, data_set)

def robot_wireless(data_set='robot_wireless'):
    # WiFi access point strengths on a tour around UW Paul Allen building.
    if not data_available(data_set):
        download_data(data_set)
    file_name = os.path.join(data_path, data_set, 'uw-floor.txt')
    all_time = np.genfromtxt(file_name, usecols=(0))
    macaddress = np.genfromtxt(file_name, usecols=(1), dtype=str)
    x = np.genfromtxt(file_name, usecols=(2))
    y = np.genfromtxt(file_name, usecols=(3))
    strength = np.genfromtxt(file_name, usecols=(4))
    addresses = np.unique(macaddress)
    times = np.unique(all_time)
    addresses.sort()
    times.sort()
    allY = np.zeros((len(times), len(addresses)))
    allX = np.zeros((len(times), 3))
    allY[:]=-92.
    strengths={}
    for address, j in zip(addresses, list(range(len(addresses)))):
        ind = np.nonzero(address==macaddress)
        temp_strengths=strength[ind]
        temp_x=x[ind]
        temp_y=y[ind]
        temp_times = all_time[ind]
        for time in temp_times:
            vals = time==temp_times
            if any(vals):
                ind2 = np.nonzero(vals)
                i = np.nonzero(time==times)
                allY[i, j] = temp_strengths[ind2]
                allX[i, 0] = time
                allX[i, 1] = temp_x[ind2]
                allX[i, 2] = temp_y[ind2]
    allY = (allY + 85.)/15.

    X = allX[0:215, :]
    Y = allY[0:215, :]

    Xtest = allX[215:, :]
    Ytest = allY[215:, :]
    return data_details_return({'X': X, 'Y': Y, 'Xtest': Xtest, 'Ytest': Ytest, 'addresses' : addresses, 'times' : times, 'covariates': [timestamp('time', '%H:%M:%S.%f'), 'X', 'Y'], 'response': addresses}, data_set)

def silhouette(data_set='ankur_pose_data'):
    """Ankur Agarwal and Bill Trigg's silhoutte data."""
    if not data_available(data_set):
        download_data(data_set)
    mat_data = scipy.io.loadmat(os.path.join(data_path, data_set, 'ankurDataPoseSilhouette.mat'))
    inMean = np.mean(mat_data['Y'])
    inScales = np.sqrt(np.var(mat_data['Y']))
    X = mat_data['Y'] - inMean
    X = X / inScales
    Xtest = mat_data['Y_test'] - inMean
    Xtest = Xtest / inScales
    Y = mat_data['Z']
    Ytest = mat_data['Z_test']
    return data_details_return({'X': X, 'Y': Y, 'Xtest': Xtest, 'Ytest': Ytest}, data_set)

def decampos_digits(data_set='decampos_characters', which_digits=[0,1,2,3,4,5,6,7,8,9]):
    """Digits data set from Teo de Campos"""
    if not data_available(data_set):
        download_data(data_set)
    path = os.path.join(data_path, data_set)
    digits = np.load(os.path.join(path, 'digits.npy'))
    digits = digits[which_digits,:,:,:]
    num_classes, num_samples, height, width = digits.shape
    Y = digits.reshape((digits.shape[0]*digits.shape[1],digits.shape[2]*digits.shape[3]))
    lbls = np.array([[l]*num_samples for l in which_digits]).reshape(Y.shape[0], 1)
    str_lbls = np.array([[str(l)]*num_samples for l in which_digits])
    return data_details_return({'Y': Y, 'lbls': lbls, 'str_lbls' : str_lbls, 'info': 'Digits data set from the de Campos characters data'}, data_set)

def ripley_synth(data_set='ripley_prnn_data'):
    """Synthetic classification data set generated by Brian Ripley for his Neural Networks book."""
    if not data_available(data_set):
        download_data(data_set)
    train = np.genfromtxt(os.path.join(data_path, data_set, 'synth.tr'), skip_header=1)
    X = train[:, 0:2]
    y = train[:, 2:3]
    test = np.genfromtxt(os.path.join(data_path, data_set, 'synth.te'), skip_header=1)
    Xtest = test[:, 0:2]
    ytest = test[:, 2:3]
    return data_details_return({'X': X, 'Y': y, 'Xtest': Xtest, 'Ytest': ytest, 'info': 'Synthetic data generated by Ripley for a two class classification problem.'}, data_set)

"""def global_average_temperature(data_set='global_temperature', num_train=1000, refresh_data=False):
    path = os.path.join(data_path, data_set)
    if data_available(data_set) and not refresh_data:
        print('Using cached version of the data set, to use latest version set refresh_data to True')
    else:
        download_data(data_set)
    data = np.loadtxt(os.path.join(data_path, data_set, 'GLBTS.long.data'))
    print('Most recent data observation from month ', data[-1, 1], ' in year ', data[-1, 0])
    allX = data[data[:, 3]!=-99.99, 2:3]
    allY = data[data[:, 3]!=-99.99, 3:4]
    X = allX[:num_train, 0:1]
    Xtest = allX[num_train:, 0:1]
    Y = allY[:num_train, 0:1]
    Ytest = allY[num_train:, 0:1]
    return data_details_return({'X': X, 'Y': Y, 'Xtest': Xtest, 'Ytest': Ytest, 'info': "Global average temperature data with " + str(num_train) + " values used as training points."}, data_set)
"""
def mauna_loa(data_set='mauna_loa', num_train=545, refresh_data=False):
    """CO2 concentrations from the Mauna Loa observatory."""
    path = os.path.join(data_path, data_set)
    if data_available(data_set) and not refresh_data:
        print('Using cached version of the data set, to use latest version set refresh_data to True')
    else:
        download_data(data_set)
    data = np.loadtxt(os.path.join(data_path, data_set, 'co2_mm_mlo.txt'))
    print('Most recent data observation from month ', data[-1, 1], ' in year ', data[-1, 0])
    allX = data[data[:, 3]!=-99.99, 2:3]
    allY = data[data[:, 3]!=-99.99, 3:4]
    X = allX[:num_train, 0:1]
    Xtest = allX[num_train:, 0:1]
    Y = allY[:num_train, 0:1]
    Ytest = allY[num_train:, 0:1]
    return data_details_return({'X': X, 'Y': Y, 'Xtest': Xtest, 'Ytest': Ytest, 'covariates': [decimalyear('year', '%Y-%m')], 'response': ['CO2/ppm'], 'info': "Mauna Loa data with " + str(num_train) + " values used as training points."}, data_set)

def osu_run1(data_set='osu_run1', sample_every=4):
    """Ohio State University's Run1 motion capture data set."""
    path = os.path.join(data_path, data_set)
    if not data_available(data_set):
        import zipfile
        download_data(data_set)
        zip = zipfile.ZipFile(os.path.join(data_path, data_set, 'run1TXT.ZIP'), 'r')
        for name in zip.namelist():
            zip.extract(name, path)
    from . import mocap
    Y, connect = mocap.load_text_data('Aug210106', path)
    Y = Y[0:-1:sample_every, :]
    return data_details_return({'Y': Y, 'connect' : connect}, data_set)

def swiss_roll_generated(num_samples=1000, sigma=0.0):
    with open(os.path.join(os.path.dirname(__file__), 'datasets', 'swiss_roll.pickle')) as f:
        if sys.version_info>=(3,0):
            import pickle
        else:
            import cPickle as pickle
        data = pickle.load(f)
    Na = data['Y'].shape[0]
    perm = np.random.permutation(np.r_[:Na])[:num_samples]
    Y = data['Y'][perm, :]
    t = data['t'][perm]
    c = data['colors'][perm, :]
    so = np.argsort(t)
    Y = Y[so, :]
    t = t[so]
    c = c[so, :]
    return {'Y':Y, 't':t, 'colors':c}


def singlecell(data_set='guo_qpcr_2010'):
    if not data_available(data_set):
        download_data(data_set)

    from pandas import read_csv
    dir_path = os.path.join(data_path, data_set)
    filename = os.path.join(dir_path, 'guo_qpcr.csv')
    Y = read_csv(filename, header=0, index_col=0)
    genes = Y.columns
    labels = Y.index
    # data = np.loadtxt(os.path.join(dir_path, 'singlecell.csv'), delimiter=",", dtype=str)
    return data_details_return({'Y': Y, 'info' : "qPCR singlecell experiment in Mouse, measuring 48 gene expressions in 1-64 cell states. The labels have been created as in Guo et al. [2010]",
                                'genes': genes, 'labels':labels,
                                }, data_set)

def swiss_roll_1000():
    return swiss_roll(num_samples=1000)

def swiss_roll(num_samples=3000, data_set='swiss_roll'):
    if not data_available(data_set):
        download_data(data_set)
    mat_data = scipy.io.loadmat(os.path.join(data_path, data_set, 'swiss_roll_data.mat'))
    Y = mat_data['X_data'][:, 0:num_samples].transpose()
    return data_details_return({'Y': Y, 'Full': mat_data['X_data'], 'info': "The first " + str(num_samples) + " points from the swiss roll data of Tennenbaum, de Silva and Langford (2001)."}, data_set)

def isomap_faces(num_samples=698, data_set='isomap_face_data'):
    if not data_available(data_set):
        download_data(data_set)
    mat_data = scipy.io.loadmat(os.path.join(data_path, data_set, 'face_data.mat'))
    Y = mat_data['images'][:, 0:num_samples].transpose()
    return data_details_return({'Y': Y, 'poses' : mat_data['poses'], 'lights': mat_data['lights'], 'info': "The first " + str(num_samples) + " points from the face data of Tennenbaum, de Silva and Langford (2001)."}, data_set)


def toy_rbf_1d(seed=default_seed, num_samples=500):
    """
    Samples values of a function from an RBF covariance with very small noise for inputs uniformly distributed between -1 and 1.

    :param seed: seed to use for random sampling.
    :type seed: int
    :param num_samples: number of samples to sample in the function (default 500).
    :type num_samples: int

    """
    import GPy
    np.random.seed(seed=seed)
    num_in = 1
    X = np.random.uniform(low= -1.0, high=1.0, size=(num_samples, num_in))
    X.sort(axis=0)
    rbf = GPy.kern.RBF(num_in, variance=1., lengthscale=np.array((0.25,)))
    white = GPy.kern.White(num_in, variance=1e-2)
    kernel = rbf + white
    K = kernel.K(X)
    y = np.reshape(np.random.multivariate_normal(np.zeros(num_samples), K), (num_samples, 1))
    return {'X':X, 'Y':y, 'info': "Sampled " + str(num_samples) + " values of a function from an RBF covariance with very small noise for inputs uniformly distributed between -1 and 1."}

def toy_rbf_1d_50(seed=default_seed):
    np.random.seed(seed=seed)
    data = toy_rbf_1d()
    indices = permute(data['X'].shape[0])
    indices = indices[0:50]
    indices.sort(axis=0)
    X = data['X'][indices, :]
    Y = data['Y'][indices, :]
    return {'X': X, 'Y': Y, 'info': "Subsamples the toy_rbf_sample with 50 values randomly taken from the original sample.", 'seed' : seed}


def toy_linear_1d_classification(seed=default_seed):
    """Simple classification data in one dimension for illustrating models."""
    def sample_class(f):
        p = 1. / (1. + np.exp(-f))
        c = np.random.binomial(1, p)
        c = np.where(c, 1, -1)
        return c

    np.random.seed(seed=seed)
    x1 = np.random.normal(-3, 5, 20)
    x2 = np.random.normal(3, 5, 20)
    X = (np.r_[x1, x2])[:, None]
    return {'X': X, 'Y':  sample_class(2.*X), 'F': 2.*X, 'covariates' : ['X'], 'response': [discrete({'positive': 1, 'negative': -1})],'seed' : seed}

def airline_delay(data_set='airline_delay', num_train=700000, num_test=100000, seed=default_seed):
    """Airline delay data used in Gaussian Processes for Big Data by Hensman, Fusi and Lawrence"""

    if not data_available(data_set):
        download_data(data_set)

    dir_path = os.path.join(data_path, data_set)
    filename = os.path.join(dir_path, 'filtered_data.pickle')

    # 1. Load the dataset
    import pandas as pd
    data = pd.read_pickle(filename)

    # WARNING: removing year
    data.pop('Year')

    # Get data matrices
    Yall = data.pop('ArrDelay').values[:,None]
    Xall = data.values

    # Subset the data (memory!!)
    all_data = num_train+num_test
    Xall = Xall[:all_data]
    Yall = Yall[:all_data]

    # Get testing points
    np.random.seed(seed=seed)
    N_shuffled = permute(Yall.shape[0])
    train, test = N_shuffled[num_test:], N_shuffled[:num_test]
    X, Y = Xall[train], Yall[train]
    Xtest, Ytest = Xall[test], Yall[test]
    covariates =  ['month', 'day of month', 'day of week', 'departure time', 'arrival time', 'air time', 'distance to travel', 'age of aircraft / years']
    response = ['delay']
    return data_details_return({'X': X, 'Y': Y, 'Xtest': Xtest, 'Ytest': Ytest, 'seed' : seed, 'info': "Airline delay data used for demonstrating Gaussian processes for big data.", 'covariates': covariates, 'response': response}, data_set)

def olivetti_faces(data_set='olivetti_faces'):
    path = os.path.join(data_path, data_set)
    if not data_available(data_set):
        import zipfile
        download_data(data_set)
        zip = zipfile.ZipFile(os.path.join(path, 'att_faces.zip'), 'r')
        for name in zip.namelist():
            zip.extract(name, path)
    Y = []
    lbls = []
    for subject in range(40):
        for image in range(10):
            image_path = os.path.join(path, 'orl_faces', 's'+str(subject+1), str(image+1) + '.pgm')
            from GPy.util import netpbmfile
            Y.append(netpbmfile.imread(image_path).flatten())
            lbls.append(subject)
    Y = np.asarray(Y)
    lbls = np.asarray(lbls)[:, None]
    return data_details_return({'Y': Y, 'lbls' : lbls, 'info': "ORL Faces processed to 64x64 images."}, data_set)

def xw_pen(data_set='xw_pen'):
    if not data_available(data_set):
        download_data(data_set)
    Y = np.loadtxt(os.path.join(data_path, data_set, 'xw_pen_15.csv'), delimiter=',')
    X = np.arange(485)[:, None]
    return data_details_return({'Y': Y, 'X': X, 'info': "Tilt data from a personalized digital assistant pen. Plot in original paper showed regression between time steps 175 and 275."}, data_set)


def download_rogers_girolami_data(data_set='rogers_girolami_data'):
    if not data_available('rogers_girolami_data'):
        import tarfile
        download_data(data_set)
        path = os.path.join(data_path, data_set)
        tar_file = os.path.join(path, 'firstcoursemldata.tar.gz')
        tar = tarfile.open(tar_file)
        print('Extracting file.')
        tar.extractall(path=path)
        tar.close()

def olympic_100m_men(data_set='rogers_girolami_data'):
    download_rogers_girolami_data()
    olympic_data = scipy.io.loadmat(os.path.join(data_path, data_set, 'data', 'olympics.mat'))['male100']

    X = olympic_data[:, 0][:, None]
    Y = olympic_data[:, 1][:, None]
    return data_details_return({'X': X, 'Y': Y,
                                'covariates' : [decimalyear('year', '%Y')],
                                'response' : ['time'],
                                 'info': "Olympic sprint times for 100 m men from 1896 until 2008. Example is from Rogers and Girolami's First Course in Machine Learning."}, data_set)

def olympic_100m_women(data_set='rogers_girolami_data'):
    download_rogers_girolami_data()
    olympic_data = scipy.io.loadmat(os.path.join(data_path, data_set, 'data', 'olympics.mat'))['female100']

    X = olympic_data[:, 0][:, None]
    Y = olympic_data[:, 1][:, None]
    return data_details_return({'X': X, 'Y': Y,
                                'covariates' : [decimalyear('year', '%Y')],
                                'response' : ['time'],
                                 'info': "Olympic sprint times for 100 m women from 1896 until 2008. Example is from Rogers and Girolami's First Course in Machine Learning."}, data_set)

def olympic_200m_women(data_set='rogers_girolami_data'):
    download_rogers_girolami_data()
    olympic_data = scipy.io.loadmat(os.path.join(data_path, data_set, 'data', 'olympics.mat'))['female200']

    X = olympic_data[:, 0][:, None]
    Y = olympic_data[:, 1][:, None]
    return data_details_return({'X': X, 'Y': Y, 'info': "Olympic 200 m winning times for women from 1896 until 2008. Data is from Rogers and Girolami's First Course in Machine Learning."}, data_set)

def olympic_200m_men(data_set='rogers_girolami_data'):
    download_rogers_girolami_data()
    olympic_data = scipy.io.loadmat(os.path.join(data_path, data_set, 'data', 'olympics.mat'))['male200']

    X = olympic_data[:, 0][:, None]
    Y = olympic_data[:, 1][:, None]
    return data_details_return({'X': X, 'Y': Y,
                                'covariates' : [decimalyear('year', '%Y')],
                                'response' : ['time'],
                                 'info': "Male 200 m winning times for women from 1896 until 2008. Data is from Rogers and Girolami's First Course in Machine Learning."}, data_set)

def olympic_400m_women(data_set='rogers_girolami_data'):
    download_rogers_girolami_data()
    olympic_data = scipy.io.loadmat(os.path.join(data_path, data_set, 'data', 'olympics.mat'))['female400']

    X = olympic_data[:, 0][:, None]
    Y = olympic_data[:, 1][:, None]
    return data_details_return({'X': X, 'Y': Y,
                                'covariates' : [decimalyear('year', '%Y')],
                                'response' : ['time'],
                                 'info': "Olympic 400 m winning times for women until 2008. Data is from Rogers and Girolami's First Course in Machine Learning."}, data_set)

def olympic_400m_men(data_set='rogers_girolami_data'):
    download_rogers_girolami_data()
    olympic_data = scipy.io.loadmat(os.path.join(data_path, data_set, 'data', 'olympics.mat'))['male400']

    X = olympic_data[:, 0][:, None]
    Y = olympic_data[:, 1][:, None]
    return data_details_return({'X': X, 'Y': Y,
                                'covariates' : [decimalyear('year', '%Y')],
                                'response' : ['time'],
                                'info': "Male 400 m winning times for women until 2008. Data is from Rogers and Girolami's First Course in Machine Learning."}, data_set)

def olympic_marathon_men(data_set='olympic_marathon_men'):
    if not data_available(data_set):
        download_data(data_set)
    olympics = np.genfromtxt(os.path.join(data_path, data_set, 'olympicMarathonTimes.csv'), delimiter=',')
    X = olympics[:, 0:1]
    Y = olympics[:, 1:2]
    return data_details_return({'X': X,
                                'Y': Y,
                                'covariates' : [decimalyear('year', '%Y')],
                                'response' : ['time'],
                                }, data_set)

def olympic_sprints(data_set='rogers_girolami_data'):
    """All olympics sprint winning times for multiple output prediction."""
    X = np.zeros((0, 2))
    Y = np.zeros((0, 1))
    cats = {}
    for i, dataset in enumerate([olympic_100m_men,
                              olympic_100m_women,
                              olympic_200m_men,
                              olympic_200m_women,
                              olympic_400m_men,
                              olympic_400m_women]):
        data = dataset()
        year = data['X']
        time = data['Y']
        X = np.vstack((X, np.hstack((year, np.ones_like(year)*i))))
        Y = np.vstack((Y, time))
        cats[dataset.__name__] = i
    data['X'] = X
    data['Y'] = Y
    data['info'] = "Olympics sprint event winning for men and women to 2008. Data is from Rogers and Girolami's First Course in Machine Learning."
    return data_details_return({
        'X': X,
        'Y': Y,
        'covariates' : [decimalyear('year', '%Y'), discrete(cats, 'event')],
        'response' : ['time'],
        'info': "Olympics sprint event winning for men and women to 2008. Data is from Rogers and Girolami's First Course in Machine Learning.",
        'output_info': {
          0:'100m Men',
          1:'100m Women',
          2:'200m Men',
          3:'200m Women',
          4:'400m Men',
          5:'400m Women'}
        }, data_set)

def movie_body_count(data_set='movie_body_count'):
    """Data set of movies and body count for movies scraped from www.MovieBodyCounts.com created by Simon Garnier and Randy Olson for exploring differences between Python and R."""
    if not data_available(data_set):
        download_data(data_set)

    from pandas import read_csv
    dir_path = os.path.join(data_path, data_set)
    filename = os.path.join(dir_path, 'film-death-counts-Python.csv')
    Y = read_csv(filename)
    Y['Actors'] = Y['Actors'].apply(lambda x: x.split('|'))
    Y['Genre'] = Y['Genre'].apply(lambda x: x.split('|'))
    Y['Director'] = Y['Director'].apply(lambda x: x.split('|'))
    return data_details_return({'Y': Y, 'info' : "Data set of movies and body count for movies scraped from www.MovieBodyCounts.com created by Simon Garnier and Randy Olson for exploring differences between Python and R.",
                                }, data_set)

def movie_body_count_r_classify(data_set='movie_body_count'):
    """Data set of movies and body count for movies scraped from www.MovieBodyCounts.com created by Simon Garnier and Randy Olson for exploring differences between Python and R."""
    data = movie_body_count()['Y']
    import pandas as pd
    import numpy as np
    X = data[['Year', 'Body_Count']]
    Y = data['MPAA_Rating']=='R' # set label to be positive for R rated films.

    # Create series of movie genres with the relevant index
    s = data['Genre'].str.split('|').apply(pd.Series, 1).stack()
    s.index = s.index.droplevel(-1) # to line up with df's index

    # Extract from the series the unique list of genres.
    genres = s.unique()

    # For each genre extract the indices where it is present and add a column to X
    for genre in genres:
        index = s[s==genre].index.tolist()
        values = pd.Series(np.zeros(X.shape[0]), index=X.index)
        values[index] = 1
        X[genre] = values
    return data_details_return({'X': X, 'Y': Y, 'info' : "Data set of movies and body count for movies scraped from www.MovieBodyCounts.com created by Simon Garnier and Randy Olson for exploring differences between Python and R. In this variant we aim to classify whether the film is rated R or not depending on the genre, the years and the body count.",
                                }, data_set)



def movielens100k(data_set='movielens100k'):
    """Data set of movie ratings collected by the University of Minnesota and 'cleaned up' for use."""
    if not data_available(data_set):
        import zipfile
        download_data(data_set)
        dir_path = os.path.join(data_path, data_set)
        zip = zipfile.ZipFile(os.path.join(dir_path, 'ml-100k.zip'), 'r')
        for name in zip.namelist():
            zip.extract(name, dir_path)
    import pandas as pd
    encoding = 'latin-1'
    movie_path = os.path.join(data_path, 'movielens100k', 'ml-100k')
    items = pd.read_csv(os.path.join(movie_path, 'u.item'), index_col = 'index', header=None, sep='|',names=['index', 'title', 'date', 'empty', 'imdb_url', 'unknown', 'Action', 'Adventure', 'Animation', 'Children''s', 'Comedy', 'Crime', 'Documentary', 'Drama', 'Fantasy', 'Film-Noir', 'Horror', 'Musical', 'Mystery', 'Romance', 'Sci-Fi', 'Thriller', 'War', 'Western'], encoding=encoding)
    users = pd.read_csv(os.path.join(movie_path, 'u.user'), index_col = 'index', header=None, sep='|', names=['index', 'age', 'sex', 'job', 'id'], encoding=encoding)
    parts = ['u1.base', 'u1.test', 'u2.base', 'u2.test','u3.base', 'u3.test','u4.base', 'u4.test','u5.base', 'u5.test','ua.base', 'ua.test','ub.base', 'ub.test']
    ratings = []
    for part in parts:
        rate_part = pd.read_csv(os.path.join(movie_path, part), index_col = 'index', header=None, sep='\t', names=['user', 'item', 'rating', 'index'], encoding=encoding)
        rate_part['split'] = part
        ratings.append(rate_part)
    Y = pd.concat(ratings)
    return data_details_return({'Y':Y, 'film_info':items, 'user_info':users, 'info': 'The Movielens 100k data'}, data_set)


def crescent_data(num_data=200, seed=default_seed):
    """
Data set formed from a mixture of four Gaussians. In each class two of the Gaussians are elongated at right angles to each other and offset to form an approximation to the crescent data that is popular in semi-supervised learning as a toy problem.

    :param num_data_part: number of data to be sampled (default is 200).
    :type num_data: int
    :param seed: random seed to be used for data generation.
    :type seed: int

    """
    np.random.seed(seed=seed)
    sqrt2 = np.sqrt(2)
    # Rotation matrix
    R = np.array([[sqrt2 / 2, -sqrt2 / 2], [sqrt2 / 2, sqrt2 / 2]])
    # Scaling matrices
    scales = []
    scales.append(np.array([[3, 0], [0, 1]]))
    scales.append(np.array([[3, 0], [0, 1]]))
    scales.append([[1, 0], [0, 3]])
    scales.append([[1, 0], [0, 3]])
    means = []
    means.append(np.array([4, 4]))
    means.append(np.array([0, 4]))
    means.append(np.array([-4, -4]))
    means.append(np.array([0, -4]))

    Xparts = []
    num_data_part = []
    num_data_total = 0
    for i in range(0, 4):
        num_data_part.append(round(((i + 1) * num_data) / 4.))
        num_data_part[i] -= num_data_total
        part = np.random.normal(size=(num_data_part[i], 2))
        part = np.dot(np.dot(part, scales[i]), R) + means[i]
        Xparts.append(part)
        num_data_total += num_data_part[i]
    X = np.vstack((Xparts[0], Xparts[1], Xparts[2], Xparts[3]))

    Y = np.vstack((np.ones((num_data_part[0] + num_data_part[1], 1)), -np.ones((num_data_part[2] + num_data_part[3], 1))))
    cats = {'negative': -1, 'positive': 1}
    return {'X':X, 'Y':Y, 'info': "Two separate classes of data formed approximately in the shape of two crescents.", 'response': [discrete(cats, 'class')]}

def creep_rupture(data_set='creep_rupture'):
    """Brun and Yoshida's metal creep rupture data."""
    if not data_available(data_set):
        import tarfile
        download_data(data_set)
        path = os.path.join(data_path, data_set)
        tar_file = os.path.join(path, 'creeprupt.tar')
        tar = tarfile.open(tar_file)
        tar.extractall(path=path)
        tar.close()
    all_data = np.loadtxt(os.path.join(data_path, data_set, 'taka'))
    y = all_data[:, 1:2].copy()
    features = [0]
    features.extend(list(range(2, 31)))
    X = all_data[:, features].copy()
    cats = {'furnace cooling': 0, 'air cooling': 1, 'oil cooling': 2, 'water quench': 3}
    attributes = ['Lifetime / hours', 'Temperature / Kelvin', 'Carbon / wt%', 'Silicon / wt%', 'Manganese / wt%', 'Phosphorus / wt%', 'Sulphur / wt%', 'Chromium / wt%', 'Molybdenum / wt%', 'Tungsten / wt%', 'Nickel / wt%', 'Copper / wt%', 'Vanadium / wt%', 'Niobium / wt%', 'Nitrogen / wt%', 'Aluminium / wt%', 'Boron / wt%', 'Cobalt / wt%', 'Tantalum / wt%', 'Oxygen / wt%', 'Normalising temperature / Kelvin', 'Normalising time / hours', discrete(cats, 'Cooling rate of normalisation'), 'Tempering temperature / Kelvin', 'Tempering time / hours', discrete(cats, 'Cooling rate of tempering'), 'Annealing temperature / Kelvin', 'Annealing time / hours', discrete(cats, 'Cooling rate of annealing'), 'Rhenium / wt%']
    return data_details_return({'X': X, 'Y': y, 'covariates' : attributes, 'response': ['Rupture stress / MPa']}, data_set)

def ceres(data_set='ceres'):
    """Twenty two observations of the Dwarf planet Ceres as observed by Giueseppe Piazzi and published in the September edition of Monatlicher Correspondenz in 1801. These were the measurements used by Gauss to fit a model of the planets orbit through which the planet was recovered three months later."""
    if not data_available(data_set):
        download_data(data_set)
    import pandas as pd
    data = pd.read_csv(os.path.join(data_path, data_set, 'ceresData.txt'), index_col = 'Tag', header=None, sep='\t',names=['Tag', 'Mittlere Sonnenzeit', 'Gerade Aufstig in Zeit', 'Gerade Aufstiegung in Graden', 'Nordlich Abweich', 'Geocentrische Laenger', 'Geocentrische Breite', 'Ort der Sonne + 20" Aberration', 'Logar. d. Distanz'], parse_dates=True, dayfirst=False)
    return data_details_return({'data': data}, data_set)


def cmu_mocap_49_balance(data_set='cmu_mocap'):
    """Load CMU subject 49's one legged balancing motion that was used by Alvarez, Luengo and Lawrence at AISTATS 2009."""
    train_motions = ['18', '19']
    test_motions = ['20']
    data = cmu_mocap('49', train_motions, test_motions, sample_every=4, data_set=data_set)
    data['info'] = "One legged balancing motions from CMU data base subject 49. As used in Alvarez, Luengo and Lawrence at AISTATS 2009. It consists of " + data['info']
    return data

def cmu_mocap_35_walk_jog(data_set='cmu_mocap'):
    """Load CMU subject 35's walking and jogging motions, the same data that was used by Taylor, Roweis and Hinton at NIPS 2007. but without their preprocessing. Also used by Lawrence at AISTATS 2007."""
    train_motions = ['01', '02', '03', '04', '05', '06',
                '07', '08', '09', '10', '11', '12',
                '13', '14', '15', '16', '17', '19',
                '20', '21', '22', '23', '24', '25',
                '26', '28', '30', '31', '32', '33', '34']
    test_motions = ['18', '29']
    data = cmu_mocap('35', train_motions, test_motions, sample_every=4, data_set=data_set)
    data['info'] = "Walk and jog data from CMU data base subject 35. As used in Tayor, Roweis and Hinton at NIPS 2007, but without their pre-processing (i.e. as used by Lawrence at AISTATS 2007). It consists of " + data['info']
    return data



def cmu_mocap(subject, train_motions, test_motions=[], sample_every=4, data_set='cmu_mocap'):
    """Load a given subject's training and test motions from the CMU motion capture data."""
    # Load in subject skeleton.
    from . import mocap
    subject_dir = os.path.join(data_path, data_set)

    # Make sure the data is downloaded.
    all_motions = train_motions + test_motions
    resource = cmu_urls_files(([subject], [all_motions]))
    data_resources[data_set] = data_resources['cmu_mocap_full'].copy()
    data_resources[data_set]['files'] = resource['files']
    data_resources[data_set]['urls'] = resource['urls']
    if resource['urls']:
        download_data(data_set)
    skel = mocap.acclaim_skeleton(os.path.join(subject_dir, subject + '.asf'))

    # Set up labels for each sequence
    exlbls = np.eye(len(train_motions))

    # Load sequences
    tot_length = 0
    temp_Y = []
    temp_lbls = []
    for i in range(len(train_motions)):
        temp_chan = skel.load_channels(os.path.join(subject_dir, subject + '_' + train_motions[i] + '.amc'))
        temp_Y.append(temp_chan[::sample_every, :])
        temp_lbls.append(np.tile(exlbls[i, :], (temp_Y[i].shape[0], 1)))
        tot_length += temp_Y[i].shape[0]

    Y = np.zeros((tot_length, temp_Y[0].shape[1]))
    lbls = np.zeros((tot_length, temp_lbls[0].shape[1]))

    end_ind = 0
    for i in range(len(temp_Y)):
        start_ind = end_ind
        end_ind += temp_Y[i].shape[0]
        Y[start_ind:end_ind, :] = temp_Y[i]
        lbls[start_ind:end_ind, :] = temp_lbls[i]
    if len(test_motions) > 0:
        temp_Ytest = []
        temp_lblstest = []

        testexlbls = np.eye(len(test_motions))
        tot_test_length = 0
        for i in range(len(test_motions)):
            temp_chan = skel.load_channels(os.path.join(subject_dir, subject + '_' + test_motions[i] + '.amc'))
            temp_Ytest.append(temp_chan[::sample_every, :])
            temp_lblstest.append(np.tile(testexlbls[i, :], (temp_Ytest[i].shape[0], 1)))
            tot_test_length += temp_Ytest[i].shape[0]

        # Load test data
        Ytest = np.zeros((tot_test_length, temp_Ytest[0].shape[1]))
        lblstest = np.zeros((tot_test_length, temp_lblstest[0].shape[1]))

        end_ind = 0
        for i in range(len(temp_Ytest)):
            start_ind = end_ind
            end_ind += temp_Ytest[i].shape[0]
            Ytest[start_ind:end_ind, :] = temp_Ytest[i]
            lblstest[start_ind:end_ind, :] = temp_lblstest[i]
    else:
        Ytest = None
        lblstest = None

    info = 'Subject: ' + subject + '. Training motions: '
    for motion in train_motions:
        info += motion + ', '
    info = info[:-2]
    if len(test_motions) > 0:
        info += '. Test motions: '
        for motion in test_motions:
            info += motion + ', '
        info = info[:-2] + '.'
    else:
        info += '.'
    if sample_every != 1:
        info += ' Data is sub-sampled to every ' + str(sample_every) + ' frames.'
    return data_details_return({'Y': Y, 'lbls' : lbls, 'Ytest': Ytest, 'lblstest' : lblstest, 'info': info, 'skel': skel}, data_set)


def mcycle(data_set='mcycle', seed=default_seed):
    if not data_available(data_set):
        download_data(data_set)

    np.random.seed(seed=seed)
    data = pd.read_csv(os.path.join(data_path, data_set, 'motor.csv'))
    data = data.reindex(permute(data.shape[0])) # Randomize so test isn't at the end

    X = data['times'].values[:, None]
    Y = data['accel'].values[:, None]

    return data_details_return({'X': X, 'Y' : Y, 'covariates' : ['times'], 'response' : ['acceleration']}, data_set)

def elevators(data_set='elevators', seed=default_seed):
    if not data_available(data_set):
        import tarfile
        download_data(data_set)
        dir_path = os.path.join(data_path, data_set)
        tar = tarfile.open(name=os.path.join(dir_path, 'elevators.tgz'))
        tar.extractall(dir_path)
        tar.close()

    elevator_path = os.path.join(data_path, 'elevators', 'Elevators')
    elevator_train_path = os.path.join(elevator_path, 'elevators.data')
    elevator_test_path = os.path.join(elevator_path, 'elevators.test')
    train_data = pd.read_csv(elevator_train_path, header=None)
    test_data = pd.read_csv(elevator_test_path, header=None)
    data = pd.concat([train_data, test_data])

    np.random.seed(seed=seed)
    # Want to choose test and training data sizes, so just concatenate them together and mix them up
    data = data.reset_index()
    data = data.reindex(permute(data.shape[0])) # Randomize so test isn't at the end

    X = data.iloc[:, :-1].values
    Y = data.iloc[:, -1].values[:, None]

    return data_details_return({'X': X, 'Y' : Y}, data_set)

if False:

    def hapmap3(data_set='hapmap3'):
        """
        The HapMap phase three SNP dataset - 1184 samples out of 11 populations.

        SNP_matrix (A) encoding [see Paschou et all. 2007 (PCA-Correlated SNPs...)]:
        Let (B1,B2) be the alphabetically sorted bases, which occur in the j-th SNP, then

              /  1, iff SNPij==(B1,B1)
        Aij = |  0, iff SNPij==(B1,B2)
              \ -1, iff SNPij==(B2,B2)

        The SNP data and the meta information (such as iid, sex and phenotype) are
        stored in the dataframe datadf, index is the Individual ID,
        with following columns for metainfo:

            * family_id   -> Family ID
            * paternal_id -> Paternal ID
            * maternal_id -> Maternal ID
            * sex         -> Sex (1=male; 2=female; other=unknown)
            * phenotype   -> Phenotype (-9, or 0 for unknown)
            * population  -> Population string (e.g. 'ASW' - 'YRI')
            * rest are SNP rs (ids)

        More information is given in infodf:

            * Chromosome:
                - autosomal chromosemes                -> 1-22
                - X    X chromosome                    -> 23
                - Y    Y chromosome                    -> 24
                - XY   Pseudo-autosomal region of X    -> 25
                - MT   Mitochondrial                   -> 26
            * Relative Positon (to Chromosome) [base pairs]
        """
        try:
            from pandas import read_pickle, DataFrame
            from sys import stdout
            import bz2
            if sys.version_info>=(3,0):
                import pickle
            else:
                import cPickle as pickle
        except ImportError as i:
            raise i("Need pandas for hapmap dataset, make sure to install pandas (http://pandas.pydata.org/) before loading the hapmap dataset")

        dir_path = os.path.join(data_path,'hapmap3')
        hapmap_file_name = 'hapmap3_r2_b36_fwd.consensus.qc.poly'
        unpacked_files = [os.path.join(dir_path, hapmap_file_name+ending) for ending in ['.ped', '.map']]
        unpacked_files_exist = reduce(lambda a, b:a and b, list(map(os.path.exists, unpacked_files)))

        if not unpacked_files_exist and not data_available(data_set):
            download_data(data_set)

        preprocessed_data_paths = [os.path.join(dir_path,hapmap_file_name + file_name) for file_name in \
                                   ['.snps.pickle',
                                    '.info.pickle',
                                    '.nan.pickle']]

        if not reduce(lambda a,b: a and b, list(map(os.path.exists, preprocessed_data_paths))):
            if not overide_manual_authorize and not prompt_stdin("Preprocessing requires ~25GB "
                                "of memory and can take a (very) long time, continue? [Y/n]"):
                print("Preprocessing required for further usage.")
                return
            status = "Preprocessing data, please be patient..."
            print(status)
            def write_status(message, progress, status):
                stdout.write(" "*len(status)); stdout.write("\r"); stdout.flush()
                status = r"[{perc: <{ll}}] {message: <13s}".format(message=message, ll=20,
                                                                   perc="="*int(20.*progress/100.))
                stdout.write(status); stdout.flush()
                return status
            if not unpacked_files_exist:
                status=write_status('unpacking...', 0, '')
                curr = 0
                for newfilepath in unpacked_files:
                    if not os.path.exists(newfilepath):
                        filepath = newfilepath + '.bz2'
                        file_size = os.path.getsize(filepath)
                        with open(newfilepath, 'wb') as new_file, open(filepath, 'rb') as f:
                            decomp = bz2.BZ2Decompressor()
                            file_processed = 0
                            buffsize = 100 * 1024
                            for data in iter(lambda : f.read(buffsize), b''):
                                new_file.write(decomp.decompress(data))
                                file_processed += len(data)
                                status=write_status('unpacking...', curr+12.*file_processed/(file_size), status)
                    curr += 12
                    status=write_status('unpacking...', curr, status)
                    os.remove(filepath)
            status=write_status('reading .ped...', 25, status)
            # Preprocess data:
            snpstrnp = np.loadtxt(unpacked_files[0], dtype=str)
            status=write_status('reading .map...', 33, status)
            mapnp = np.loadtxt(unpacked_files[1], dtype=str)
            status=write_status('reading relationships.txt...', 42, status)
            # and metainfo:
            infodf = DataFrame.from_csv(os.path.join(dir_path,'./relationships_w_pops_121708.txt'), header=0, sep='\t')
            infodf.set_index('IID', inplace=1)
            status=write_status('filtering nan...', 45, status)
            snpstr = snpstrnp[:,6:].astype('S1').reshape(snpstrnp.shape[0], -1, 2)
            inan = snpstr[:,:,0] == '0'
            status=write_status('filtering reference alleles...', 55, status)
            ref = np.array([np.unique(x)[-2:] for x in snpstr.swapaxes(0,1)[:,:,:]])
            status=write_status('encoding snps...', 70, status)
            # Encode the information for each gene in {-1,0,1}:
            status=write_status('encoding snps...', 73, status)
            snps = (snpstr==ref[None,:,:])
            status=write_status('encoding snps...', 76, status)
            snps = (snps*np.array([1,-1])[None,None,:])
            status=write_status('encoding snps...', 78, status)
            snps = snps.sum(-1)
            status=write_status('encoding snps...', 81, status)
            snps = snps.astype('i8')
            status=write_status('marking nan values...', 88, status)
            # put in nan values (masked as -128):
            snps[inan] = -128
            status=write_status('setting up meta...', 94, status)
            # get meta information:
            metaheader = np.r_[['family_id', 'iid', 'paternal_id', 'maternal_id', 'sex', 'phenotype']]
            metadf = DataFrame(columns=metaheader, data=snpstrnp[:,:6])
            metadf.set_index('iid', inplace=1)
            metadf = metadf.join(infodf.population)
            metadf.to_pickle(preprocessed_data_paths[1])
            # put everything together:
            status=write_status('setting up snps...', 96, status)
            snpsdf = DataFrame(index=metadf.index, data=snps, columns=mapnp[:,1])
            with open(preprocessed_data_paths[0], 'wb') as f:
                pickle.dump(f, snpsdf, protocoll=-1)
            status=write_status('setting up snps...', 98, status)
            inandf = DataFrame(index=metadf.index, data=inan, columns=mapnp[:,1])
            inandf.to_pickle(preprocessed_data_paths[2])
            status=write_status('done :)', 100, status)
            print('')
        else:
            print("loading snps...")
            snpsdf = read_pickle(preprocessed_data_paths[0])
            print("loading metainfo...")
            metadf = read_pickle(preprocessed_data_paths[1])
            print("loading nan entries...")
            inandf = read_pickle(preprocessed_data_paths[2])
        snps = snpsdf.values
        populations = metadf.population.values.astype('S3')
        hapmap = dict(name=data_set,
                      description='The HapMap phase three SNP dataset - '
                      '1184 samples out of 11 populations. inan is a '
                      'boolean array, containing wheather or not the '
                      'given entry is nan (nans are masked as '
                      '-128 in snps).',
                      snpsdf=snpsdf,
                      metadf=metadf,
                      snps=snps,
                      inan=inandf.values,
                      inandf=inandf,
                      populations=populations)
        return hapmap

    def olivetti_glasses(data_set='olivetti_glasses', num_training=200, seed=default_seed):
        path = os.path.join(data_path, data_set)
        if not data_available(data_set):
            download_data(data_set)
        y = np.load(os.path.join(path, 'has_glasses.np'))
        y = np.where(y=='y',1,0).reshape(-1,1)
        faces = scipy.io.loadmat(os.path.join(path, 'olivettifaces.mat'))['faces'].T
        np.random.seed(seed=seed)
        index = permute(faces.shape[0])
        X = faces[index[:num_training],:]
        Xtest = faces[index[num_training:],:]
        Y = y[index[:num_training],:]
        Ytest = y[index[num_training:]]
        return data_details_return({'X': X, 'Y': Y, 'Xtest': Xtest, 'Ytest': Ytest, 'seed' : seed, 'info': "ORL Faces with labels identifiying who is wearing glasses and who isn't. Data is randomly partitioned according to given seed. Presence or absence of glasses was labelled by James Hensman."}, 'olivetti_faces')

    def simulation_BGPLVM(data_set='bgplvm_simulation'):
        mat_data = scipy.io.loadmat(os.path.join(data_path, 'BGPLVMSimulation.mat'))
        Y = np.array(mat_data['Y'], dtype=float)
        S = np.array(mat_data['initS'], dtype=float)
        mu = np.array(mat_data['initMu'], dtype=float)
        #return data_details_return({'S': S, 'Y': Y, 'mu': mu}, data_set)
        return {'Y': Y, 'S': S,
                'mu' : mu,
                'info': "Simulated test dataset generated in MATLAB to compare BGPLVM between python and MATLAB"}

    def politics_twitter(data_set='politics_twitter'):
        # Bailout before downloading!
        import tweepy
        import pandas as pd
        import time
        import progressbar as pb
        import sys

        if not data_available(data_set):
            download_data(data_set)

        # FIXME: Try catch here
        CONSUMER_KEY = config.get('twitter', 'CONSUMER_KEY')
        CONSUMER_SECRET = config.get('twitter', 'CONSUMER_SECRET')

        OAUTH_TOKEN = config.get('twitter', 'OAUTH_TOKEN')
        OAUTH_TOKEN_SECRET = config.get('twitter', 'OAUTH_TOKEN_SECRET')

        # Authenticate
        auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
        auth.set_access_token(OAUTH_TOKEN, OAUTH_TOKEN_SECRET)

        # Make tweepy api object, and be carefuly not to abuse the API!
        api = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

        requests_per_minute = int(180.0/15.0)
        save_freq = 5

        data_dict = {}
        for party in ['ukip', 'labour', 'conservative', 'greens']:
            # Load in the twitter data we want to join

            parsed_file_path = os.path.join(data_path, data_set, '{}_twitter_parsed.csv'.format(party))
            file_already_parsed = False
            if os.path.isfile(parsed_file_path):
                print("Data already scraped, loading saved scraped data for {} party".format(party))
                # Read the data
                data = pd.read_csv(parsed_file_path)
                # Check it has been fully parsed (no NATs in time)
                if data['time'].isnull().sum() == 0:
                    file_already_parsed = True

            if not file_already_parsed:
                print("Scraping tweet data from ids for the {} party data".format(party))
                sys.stdout.write("Scraping tweet data from ids for the {} party data".format(party))

                raw_file_path = os.path.join(data_path, data_set, '{}_raw_ids.csv'.format(party))
                # data = pd.read_csv('./data_download/{}_raw_ids.csv'.format(party))
                data = pd.read_csv(raw_file_path)

                #Iterate in blocks
                full_block_size = 100
                num_blocks = data.shape[0]/full_block_size + 1
                last_block_size = data.shape[0]%full_block_size

                # Progress bar to give some indication of how long we now need to wait!
                pbar = pb.ProgressBar(widgets=[
                        ' [', pb.Timer(), '] ',
                        pb.Bar(),
                        ' (', pb.ETA(), ') ',], fd=sys.stdout)

                for block_num in pbar(range(num_blocks)):
                    sys.stdout.flush()
                    # Get a single block of tweets
                    start_ind = block_num*full_block_size
                    if block_num == num_blocks - 1:
                        # end_ind = start_ind + last_block_size
                        tweet_block = data.iloc[start_ind:]
                    else:
                        end_ind = start_ind + full_block_size
                        tweet_block = data.iloc[start_ind:end_ind]

                    # Gather ther actual data, fill out the missing time
                    tweet_block_ids = tweet_block['id_str'].tolist()
                    sucess = False
                    while not sucess:
                        try:
                            tweet_block_results = api.statuses_lookup(tweet_block_ids, trim_user=True)
                            sucess = True
                        except Exception:
                            # Something went wrong with our pulling of result. Wait
                            # for a minute and try again
                            time.sleep(60.0)
                    for tweet in tweet_block_results:
                        data.ix[data['id_str'] == int(tweet.id_str), 'time'] = tweet.created_at

                    # Wait so as to stay below the rate limit
                    # Stay on the safe side, presume that collection is instantanious
                    time.sleep(60.0/requests_per_minute + 0.1)

                    if block_num % save_freq == 0:
                        data.to_csv(parsed_file_path)

                #Now convert times to pandas datetimes
                data['time'] = pd.to_datetime(data['time'])
                #Get rid of non-parsed dates
                data = data.ix[data['time'].notnull(), :]
                data.to_csv(parsed_file_path)

            data_dict[party] = data

        return data_details_return(data_dict, data_set)

    def cifar10_patches(data_set='cifar-10'):
        """The Candian Institute for Advanced Research 10 image data set. Code for loading in this data is taken from this Boris Babenko's blog post, original code available here: http://bbabenko.tumblr.com/post/86756017649/learning-low-level-vision-feautres-in-10-lines-of-code"""
        if sys.version_info>=(3,0):
            import pickle
        else:
            import cPickle as pickle
        dir_path = os.path.join(data_path, data_set)
        filename = os.path.join(dir_path, 'cifar-10-python.tar.gz')
        if not data_available(data_set):
            import tarfile
            download_data(data_set)
            # This code is from Boris Babenko's blog post.
            # http://bbabenko.tumblr.com/post/86756017649/learning-low-level-vision-feautres-in-10-lines-of-code
            tfile = tarfile.open(filename, 'r:gz')
            tfile.extractall(dir_path)

        with open(os.path.join(dir_path, 'cifar-10-batches-py','data_batch_1'),'rb') as f:
            data = pickle.load(f)

        images = data['data'].reshape((-1,3,32,32)).astype('float32')/255
        images = np.rollaxis(images, 1, 4)
        patches = np.zeros((0,5,5,3))
        for x in range(0,32-5,5):
            for y in range(0,32-5,5):
                patches = np.concatenate((patches, images[:,x:x+5,y:y+5,:]), axis=0)
        patches = patches.reshape((patches.shape[0],-1))
        return data_details_return({'Y': patches, "info" : "32x32 pixel patches extracted from the CIFAR-10 data by Boris Babenko to demonstrate k-means features."}, data_set)

    def movie_collaborative_filter(data_set='movie_collaborative_filter', date='2014-10-06'):
        """Data set of movie ratings as generated live in class by students."""
        download_data(data_set)
        from pandas import read_csv
        dir_path = os.path.join(data_path, data_set)
        filename = os.path.join(dir_path, 'film-death-counts-Python.csv')
        Y = read_csv(filename)
        return data_details_return({'Y': Y, 'info' : "Data set of movie ratings as summarized from Google doc spreadheets of students in class.",
                                    }, data_set)


