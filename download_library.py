import json
import os
import subprocess


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

for lib_name in libs_info:
    # in most cases, the last one is the latest version
    lib_version = list(libs_info[lib_name].keys())[-1]
    lib_info = libs_info[lib_name][lib_version]
    if "source" not in lib_info:
        pl(lib_name + ":" + lib_version + " does not have a source key.")
        continue
    source = lib_info["source"]
    file_path = lib_name + "_" + lib_version
    file_path = os.path.join(lib_path, file_path)

    # if file_path is exists and is not empty, then continue
    if os.path.exists(file_path) and os.listdir(file_path):
        pl(lib_name + ":" + lib_version + " has already been built.")
        continue

    with open("./cocoapods-downloader/downloader.rb", "w", encoding="UTF-8") as f:
        # require './cocoapods-downloader'

        # target_path = './'
        # options = { :git => 'https://github.com/admost/AMR-IOS-ADAPTER-MINTEGRAL.git'}
        # options = Pod::Downloader.preprocess_options(options)
        # downloader = Pod::Downloader.for_target(target_path, options)
        # downloader.download
        f.write("require './cocoapods-downloader'")
        f.write("target_path = '{}'".format(file_path))
        options = "{"
        for key in source:
            options += ":" + key + " => '" + source[key] + "'" + ","
        options = options[:-1] + "}"
        if len(options) > 4:
            pl(log_f, lib_name + ":" + lib_version + " parse source file error! " + url)
            pl(log_f, json.dumps(source))
            continue
        f.write("options = {}".format(options))
        f.write("options = Pod::Downloader.preprocess_options(options)")
        f.write("downloader = Pod::Downloader.for_target(target_path, options)")
        f.write("downloader.download")

    path = os.getcwd()
    os.chdir("./cocoapods-downloader")
    cmd = "ruby downloader.rb"
    subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, encoding='gbk')
    os.chdir(path)

    if os.path.exists(file_path) and os.listdir(file_path):
        pl(lib_name + ":" + lib_version + " has been downloaded!")
    else:
        pl(lib_name + ":" + lib_version + " download failed!")




