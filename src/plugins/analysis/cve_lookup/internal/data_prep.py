import re
import xml.etree.ElementTree as Et
from datetime import datetime
from io import BytesIO
from json import load
from typing import Tuple
from zipfile import ZipFile

import requests
from meta import get_meta, unbinding

METADATA = get_meta()


def get_cve_links(url: str) -> list:
    cve_urls = list()
    current = datetime.today().year
    for year in range(2002, current + 1):
        cve_urls.append(url.format(year))

    return cve_urls


def iterate_urls(dl_urls: list, path: str):
    request = None
    for url in dl_urls:
        try:
            request = requests.get(url, allow_redirects=True)
        except requests.exceptions.RequestException as err:
            exit('Error: URLs are invalid. URL format might have been changed or website might have moved. ' + str(err))

        zipped_data = ZipFile(BytesIO(request.content))
        zipped_data.extractall(path)


def download_cve(update: bool, download_path: str, years: list):
    if update:
        cve_candidates = [METADATA['source_urls']['cve_source'].format('modified')]
    else:
        all_cve_urls = get_cve_links(METADATA['source_urls']['cve_source'])
        if not all_cve_urls:
            exit('Error: No CVE links are provided')
        cve_candidates = [url for url in all_cve_urls for year in years if str(year) in url]

    iterate_urls(cve_candidates, download_path)


def download_cpe(download_path: str):
    cpe_url = METADATA['source_urls']['cpe_source']
    if not cpe_url:
        exit('Error: No CPE URL provided. Check metadata.json if required URL is set.')
    iterate_urls([cpe_url], download_path)


def iterate_nodes(nodes: list, cpe_entries: list) -> list:
    for dicts in nodes:
        if 'cpe_match' in dicts.keys():
            for cpe in dicts['cpe_match']:
                if cpe['vulnerable'] is True:
                    cpe_entries.append(cpe['cpe23Uri'])
        elif 'children' in dicts.keys():
            iterate_nodes(dicts['children'], cpe_entries)

    return cpe_entries


def extract_data_from_cve(root: dict) -> Tuple[list, list]:
    cve_list, summary_list = list(), list()
    for feed in root['CVE_Items']:
        cpe_entries = list()
        cve_id = feed['cve']['CVE_data_meta']['ID']
        summary = feed['cve']['description']['description_data'][0]['value']
        if feed['configurations']['nodes']:
            cve_list.append(cve_id)
            cpe_entries = list(set(iterate_nodes(feed['configurations']['nodes'], cpe_entries)))
            cve_list.extend(cpe_entries)
        elif not summary.startswith('** REJECT **'):
            summary_list.extend([cve_id, summary])

    return cve_list, summary_list


def extract_cve(file: str) -> Tuple[list, list]:
    feeds, root = None, None

    try:
        feeds = open(file)
        root = load(feeds)
    except IOError as err:
        raise err
    finally:
        feeds.close()

    return extract_data_from_cve(root)


def extract_cpe(file: str) -> list:
    cpe_list = []
    tree = None

    try:
        tree = Et.parse(file)
    except Et.ParseError as err:
        exit(err)
    root = tree.getroot()

    for entry in root:
        for item in entry:
            if 'cpe23-item' in item.tag:
                cpe_list.append(item.attrib['name'])

    return cpe_list


def setup_cve_feeds_table(cve_list: list) -> list:
    cve_table, row = list(), list()
    ident = ''

    for entry in cve_list:
        if re.match(r'CVE-[0-9]{4}-[0-9]', entry):
            ident = entry
        else:
            row.append(ident)
            year = ident.split('-')[1]
            row.append(year)
            row.append(entry)
            row.extend(unbinding(re.split(r'(?<!\\)[:]', entry)[2:]))
            cve_table.append(tuple(row))
            row = list()

    return cve_table


def setup_cve_summary_table(summary_list: list) -> list:
    cve_summary_table, row = list(), list()

    for entry in summary_list:
        if re.match(r'CVE-[0-9]{4}-[0-9]', entry):
            row.append(entry)
            year = entry.split('-')[1]
            row.append(year)
        else:
            row.append(entry)
            cve_summary_table.append(tuple(row))
            row = list()

    return cve_summary_table


def setup_cpe_table(cpe_list: list) -> list:
    cpe_table = []
    for cpe in cpe_list:
        row = unbinding(re.split(r'(?<!\\)[:]', cpe)[2:])
        row.insert(0, cpe)
        cpe_table.append(tuple(row))

    return cpe_table
