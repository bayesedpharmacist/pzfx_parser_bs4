"""Package to load and parse tables from a Prism pzfx file (version: 9.4.0.673) with BeutifulSoup"""
#!/usr/bin/env python3

import pandas as pd
import numpy as np
from itertools import count, chain, cycle
from bs4 import BeautifulSoup

class PrismFileLoadError(Exception):
    pass

def _subcolumn_to_numpy(subcolumn):
    try:
        data = []
        for d in subcolumn.find_all('d'):
            if not (('Excluded' in d) and (d['Excluded'] == '1')):
                if d.text == '':
                    data.append(None)
                else:
                    data.append(float(d.text))
            else:
                data.append(np.nan)
    except Exception as a:  # If data can't be read silently fail
        print("Couldn't Read a column in the file because: %s" % a)
        data = None

    return np.array(data)

def _parse_xy_table(table):
    xformat = table['XFormat']
    try:
        yformat = table['YFormat']
    except KeyError:
        yformat = None
    evformat = table['EVFormat']

    xscounter = count()
    xsubcolumn_names = lambda: str(next(xscounter))
    if yformat == 'SEN':
        yslist = cycle(['Mean', 'SEM', 'N'])
        ysubcolumn_names = lambda: next(yslist)
    elif yformat == 'upper-lower-limits':
        yslist = cycle(['Mean', 'Lower', 'Upper'])
        ysubcolumn_names = lambda: next(yslist)
    else:
        yscounter = count()
        ysubcolumn_names = lambda: str(next(yscounter))

    columns = {}
    for xcolumn in chain(table.find_all('XColumn'), table.find_all('XAdvancedColumn')):
        xcolumn_name = 'Xcol'
        for subcolumn in xcolumn.find_all('Subcolumn'):
            subcolumn_name = xcolumn_name + '_' + xsubcolumn_names()
            columns[subcolumn_name] = _subcolumn_to_numpy(subcolumn)
    for ycolumn in chain(table.find_all('YColumn'), table.find_all('YAdvancedColumn')):
        ycolumn_name = ycolumn.find('Title').text
        for subcolumn in ycolumn.find_all('Subcolumn'):
            subcolumn_name = ycolumn_name + '_' + ysubcolumn_names()
            columns[subcolumn_name] = _subcolumn_to_numpy(subcolumn)

    maxlength = max([v.shape[0] if v.shape != () else 0 for v in columns.values()])
    for k, v in columns.items():
        if v.shape != ():
            if v.shape[0] < maxlength:
                columns[k] = np.pad(v, (0, maxlength - v.shape[0]), mode='constant', constant_values=np.nan)
        else:
            columns[k] = np.pad(v, (0, maxlength - 0), mode='constant', constant_values=np.nan)

    return pd.DataFrame(columns)

def _parse_table_to_dataframe(table):
    tabletype = table['TableType']

    if tabletype == 'XY' or tabletype == 'TwoWay' or tabletype == 'OneWay':
        df = _parse_xy_table(table)
    else:
        raise PrismFileLoadError('Cannot parse %s tables for now!' % tabletype)

    return df

def read_pzfx(filename):
    """Open and parse the Prism pzfx file given in `filename`.
    Returns a dictionary containing table names as keys and pandas DataFrames as values."""
    with open(filename, 'r') as f:
        data = f.read()
    xml_form = BeautifulSoup(data, "xml")


    if xml_form.GraphPadPrismFile.attrs['PrismXMLVersion'] != '5.00':
        raise PrismFileLoadError('Can only load Prism files with XML version 5.00!')

    tables = {table.find('Title').text: _parse_table_to_dataframe(table)
              for table in xml_form.find_all('Table')}

    return tables