import gzip
import re
import requests
import ipaddress
from datetime import datetime


def date_to_date_object(date: str):
    date = date.strip('[')
    date = date.strip()
    format_string = '%d/%b/%Y:%H:%M:%S %z'
    obj = datetime.strptime(date, format_string)
    return obj
    

def find_edge_dates(info: list):
    dates = []
    for inf in info: 
        if inf['is_download']:
            date = date_to_date_object(inf['date'])
            dates.append((date, inf['line']))
    
    max = dates[0]
    min = dates[len(dates) - 1]
    for date in dates:
        if date[0] > max[0]:
            max = date
        if date[0] < min[0]:
            min = date
    
    return (max, min)
    
    
def get_github_runner_ips():
    url = "https://api.github.com/meta"
    data = requests.get(url).json()
    return data.get("actions", [])


ip_list = get_github_runner_ips()
ip_list = [ipaddress.ip_network(ip) for ip in ip_list]

count = 0

def check_ci_runner(ip: str) -> bool:
    global count
    ip = ipaddress.ip_address(ip)
    for ip_check in ip_list:
        if ip in ip_check:
            count += 1
            return True

    return False


def count_frequencies(info: list) -> dict:
    frequencies = {'Total with CI': 0, 'Total': 0}
    for i in range(len(info)):
        if re.search(r'qiime2-\d{4}\.\d+\.\d+', info[i]['line']):
            frequencies['Total'] += 1
            if info[i]['distribution'] in frequencies:
                frequencies[info[i]['distribution']] += 1
            else:
                frequencies[info[i]['distribution']] = 1
    
    frequencies['Total with CI'] = frequencies['Total'] + count
    
    return frequencies
    

logs = ["access-logs/access.log." + str(i) + ".gz" for i in range(1, 52)]


def split_line(line: str) -> dict:
    info = {'is_download': False, 'line': line, 'distribution': None}
    ip = line.split()[0]
    info['ip'] = ip

    date = re.search(r'\[(.*?)\]', line)
    date = date[0] if date else None
    date = date.strip(']') if date else None
    info['date'] = date
    method = re.search(r'(GET|HEAD|POST)', line)
    method = method[0] if method else None
    info['method'] = method

    download = re.search(r'\.tar|\.whl|\.conda|\.qza|\.qzv|\.yml|\.yaml', line)
    if download:
        info['is_download'] = True

    if re.search(r'jupyterbooks', line):
        info['version'] = 'N/A'
        info['is_download'] = False

    else:
        version = re.search(r'/\d+\.\d+/', line)
        version = version[0] if version else None
        version = version.strip('/') if version else None
        info['version'] = version

    if not info['version']:
        version = re.search(r'qiime2/latest/', line)
        version = version[0] if version else None
        version = version.split('qiime2/')[1] if version else None
        version = version.strip('/') if version else None
        info['version'] = version

    distribution = re.search(
        r'amplicon|metagenome|pathogenome|tiny|shotgun|fmt', line
    )

    distribution = distribution[0] if distribution else None
    info['distribution'] = distribution

    if info['distribution']:
        if check_ci_runner(info['ip']):
            return {}
    
    return info


def read_logs(logs: list) -> list:
    info = []
    for log in logs:
        with gzip.open(log) as log:
            lines = log.readlines()
            for line in lines:
                line = line.decode("utf-8")
                temp = split_line(line)
                if temp:
                    info.append(temp)

    return info


def check_version(info: list) -> bool:
    flag = True
    for info in info:
        if not info['is_download']:
            flag = False

    return flag


def to_downloads(info: list) -> list:
    return [inf for inf in info if inf.get('is_download')]


info_temp = read_logs(logs)
distributions_count = count_frequencies(info_temp)

print(distributions_count)

edge_dates = find_edge_dates(info_temp)
print('Most recent download:')
print(edge_dates[0][0])
print('Oldest download:')
print(edge_dates[1][0])
