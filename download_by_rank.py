import argparse
import json
import logging
import os
import re
import shutil
import subprocess
from asyncio import as_completed
from concurrent.futures import ThreadPoolExecutor

import pymongo

import utils


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
                return lib_name + ":" + lib_version + " parse source file error! undefined source key type!"
        options = options[:-1] + "}"
        if len(options) <= 5:
            return lib_name + ":" + lib_version + " parse source file error!\n" + json.dumps(source)
        f.write("options = {}\n".format(options))
        f.write("options = Pod::Downloader.preprocess_options(options)\n")
        f.write("downloader = Pod::Downloader.for_target(target_path, options)\n")
        f.write("downloader.download\n")
    try:
        cmd = "./cocoapods-downloader/downloader.exp " + down_file
        ret = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, encoding='gbk')
        ret.wait()
    except Exception as e:
        return lib_name + ":" + lib_version + " " + e.args[0]

    if os.path.exists("./cocoapods-downloader/" + down_file):
        os.remove("./cocoapods-downloader/" + down_file)

    if os.path.exists(file_path) and os.listdir(file_path):
        return lib_name + ":" + lib_version + " has been downloaded!"
    else:
        if os.path.exists(file_path): shutil.rmtree(file_path)
        return lib_name + ":" + lib_version + " download failed!"


def main(max_workers):

    logger = utils.config_log(name=__name__, level=logging.INFO, log_path="./logs/{}.log".format(os.path.basename(__file__).replace(".py", "")))
    client = pymongo.MongoClient("mongodb://%s:%s@code-analysis.org:%s" % (os.environ.get("MONGOUSER"), os.environ.get("MONGOPASS"), os.environ.get("MONGOPORT")))
    db = client["lib"]
    lib_source_info = db["lib_source_info"]
    lib_rank_info = db["lib_rank_info"]
    rank_info = lib_rank_info.find().sort([("forks_count", pymongo.DESCENDING), ("stargazers_count", pymongo.DESCENDING), ("updated_at", pymongo.DESCENDING)])
    task = []
    with ThreadPoolExecutor(max_workers) as threadPool:
        for lib in rank_info:
            if "name" not in lib:
                logger.info("Could not find useful information. details: {0}".format(json.dumps(lib)))
                continue
            lib_name = lib["name"]
            for lib_details in lib_source_info.find({"name": lib_name}):
                lib_version = lib_details["version"]
                if "source" not in lib_details:
                    logger.info(lib_name + ":" + lib_version + " does not have a source field.")
                    continue
                source = lib_details["source"]
                future = threadPool.submit(download, lib_name, lib_version, source)
                task.append(future)

        for future in as_completed(task):
            logger.info(future.result())
            # limit the space, du -sh is too slow, so we use the df -lh
            ret = subprocess.Popen("df -lh", shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, encoding='gbk')
            ret.wait()
            ret = ret.stdout.read()
            space = re.findall(r"/dev/sda2 *\w*? *\w*? *(\w*?) *[0-9]+%", ret)
            if len(space) > 0:
                if int(space[0][:-1]) > 50:
                    continue
                logger.info("space is less than 50G")
                for t in task:
                    if not t.done(): t.cancel()
    logger.info("done!")
    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='The downloader that download by rank for libraries.')
    parser.add_argument('--max_workers', type=int, default=10, help="the max workers of threadPool.")
    args = parser.parse_args()
    main(args.max_workers)

