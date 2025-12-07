import gzip
import re
import requests
import ipaddress


def get_github_runner_ips():
    url = "https://api.github.com/meta"
    data = requests.get(url).json()
    return data.get("actions", [])

ip_list = get_github_runner_ips()
ip_list = [ipaddress.ip_network(ip) for ip in ip_list]

def check_ci_runner(ip: str) -> bool:
    ip = ipaddress.ip_address(ip)
    for ip_check in ip_list:
        if ip in ip_check:
            return True

    return False

def count_frequencies_ip(info: list, type: str)->list:
    data_dict = {'total': 0}

    for i in range(len(info)):
        try:
            if info[i]['ip'] == info[i+1]['ip'] and info[i][type] == info[i+1][type]:
                continue
            else:
                if info[i][type] in data_dict.keys():
                    data_dict[info[i][type]] += 1
                else:
                    data_dict[info[i][type]] = 1
                data_dict['total'] += 1
        except IndexError:
            if info[i][type] in data_dict.keys():
                data_dict[info[i][type]] += 1
            else:
                data_dict[info[i][type]] = 1
                data_dict['total'] += 1


    data_list = data_dict.items()

    data_list= sorted(data_list, key=lambda x: x[1], reverse=True)

    return data_list

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

    download = re.search('\.tar|\.whl|\.conda|\.qza|\.qzv|\.yml|\.yaml', line)
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
        r'amplicon|metagenome|pathogenome|tiny|shotgun', line
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
distributions_count = count_frequencies_ip(info_temp, 'distribution')

print(distributions_count)