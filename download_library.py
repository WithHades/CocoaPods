import json
import os
import subprocess

import requests


def run_command(cmd):
    return None
    return subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='gbk').communicate()[0]


# print and log
def pl(f, msg):
    print(msg)
    f.write(msg + "\n")


with open("./libs_info.json", "r", encoding="UTF-8") as f:
    libs_info = json.load(f)

log_f = open("./log.log", "w", encoding="UTF-8")

lib_path = "../libraries"
if not os.path.exists(lib_path):
    os.mkdir(lib_path)
os.chdir(lib_path)

for lib_name in libs_info:
    # in most cases, the last one is the latest version
    lib_version = list(libs_info[lib_name].keys())[-1]
    lib_info = libs_info[lib_name][lib_version]
    if "source" not in lib_info:
        pl(lib_name + ":" + lib_version + " does not have a source")
        continue

    source = lib_info["source"]
    if "git" in source:
        git = source["git"]
        file_path = git[git.rfind("/") + 1 : git.rfind(".")]
        if file_path == "":
            pl(log_f, lib_name + ":" + lib_version + " does not find the git file path")
            continue
        if os.path.exists(file_path):
            continue
        if "tag" in source:
            run_command("git clone -b {} --depth=1 {}".format(source["tag"], git))
        else:
            run_command("git clone {}".format(git))
        if not os.path.exists(file_path):
            pl(log_f, lib_name + ":" + lib_version + " downloaded failed from " + git)
        continue

    if "http" in source:
        url = source["http"]
        file_path = url[url.rfind("/") + 1:]
        if os.path.exists(file_path):
            continue
        continue
        try:
            res = requests.get(url)
            if res.status_code != 200:
                pl(log_f, lib_name + ":" + lib_version + " downloaded failed from " + url)
                continue
            with open(file_path, 'wb') as f:
                f.write(res.content)
        except Exception as e:
            pass
        if not os.path.exists(file_path):
            pl(log_f, lib_name + ":" + lib_version + " downloaded failed from " + url)
        continue
    print(source, 33333)


