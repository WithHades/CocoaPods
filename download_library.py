import json
import os
import re
import shutil
import subprocess

from concurrent.futures import ThreadPoolExecutor, as_completed


# print and log
def pl(f, msg):
    print(msg)
    f.write(msg + "\n")


def download(lib_name, lib_version, source):
    lib_path = "../libraries"
    file_path = lib_name + "_" + lib_version
    file_path = os.path.join(lib_path, file_path)

    # if file_path is exists and is not empty, then return
    if os.path.exists(file_path) and os.listdir(file_path):
        return lib_name + ":" + lib_version + " has already been built."

    down_file = "d_" + lib_name + "_" + lib_version + ".rb"
    with open("./cocoapods-downloader/" + down_file, "w", encoding="UTF-8") as f:
        # require './cocoapods-downloader'

        # target_path = './'
        # options = { :git => 'https://github.com/admost/AMR-IOS-ADAPTER-MINTEGRAL.git'}
        # options = Pod::Downloader.preprocess_options(options)
        # downloader = Pod::Downloader.for_target(target_path, options)
        # downloader.download
        f.write("require './cocoapods-downloader'\n")
        f.write("target_path = '{}'\n".format("../" + file_path))
        options = "{"
        for key in source:
            if isinstance(source[key], (str, int, float, bool)):
                options += ":" + key + " => '" + str(source[key]).lower() + "'" + ","
            elif isinstance(source[key], list):
                if len(source[key]) > 0:
                    # {'headers': ['Authorization: Bearer QQ==']}
                    options += "," + key + " => '" + str(source[key][0]).lower() + "'" + ","
            else:
                pl(log_f, lib_name + ":" + lib_version + " parse source file error! undefined source key type!")
        options = options[:-1] + "}"
        if len(options) <= 5:
            return lib_name + ":" + lib_version + " parse source file error!\n" + json.dumps(source)
        f.write("options = {}\n".format(options))
        f.write("options = Pod::Downloader.preprocess_options(options)\n")
        f.write("downloader = Pod::Downloader.for_target(target_path, options)\n")
        f.write("downloader.download\n")

    cmd = "./cocoapods-downloader/downloader.exp " + down_file
    ret = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, encoding='gbk')
    ret.wait()

    if os.path.exists("./cocoapods-downloader/" + down_file):
        os.remove("./cocoapods-downloader/" + down_file)

    if os.path.exists(file_path) and os.listdir(file_path):
        return lib_name + ":" + lib_version + " has been downloaded!"
    else:
        if os.path.exists(file_path): shutil.rmtree(file_path)
        return lib_name + ":" + lib_version + " download failed!"


with open("./libs_info.json", "r", encoding="UTF-8") as f:
    libs_info = json.load(f)

log_f = open("./log.log", "w", encoding="UTF-8")

lib_path = "../libraries"
if not os.path.exists(lib_path):
    os.mkdir(lib_path)


max_workers = 10
task = []
with ThreadPoolExecutor(max_workers) as threadPool:
    for lib_name in libs_info:
        # in most cases, the last one is the latest version
        lib_version = list(libs_info[lib_name].keys())[-1]
        lib_info = libs_info[lib_name][lib_version]

        if "source" not in lib_info:
            pl(log_f, lib_name + ":" + lib_version + " does not have a source key.")
            continue
        source = lib_info["source"]
        future = threadPool.submit(download, lib_name, lib_version, source)
        task.append(future)

    for future in as_completed(task):
        pl(log_f, future.result())
        # limit the space, du -sh is too slow, so we use the df -lh
        ret = subprocess.Popen("df -lh", shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, encoding='gbk')
        ret.wait()
        ret = ret.stdout.read()
        space = re.findall(r"/dev/sda2 *\w*? *\w*? *(\w*?) *[0-9]+%", ret)
        if len(space) > 0:
            if int(space[0][:-1]) > 50:
                continue
            pl(log_f, "space is less than 50G")
            for t in task:
                if not t.done(): t.cancel()
            log_f.close()
            exit(0)
log_f.close()


