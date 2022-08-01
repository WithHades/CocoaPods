import argparse
import json
import logging
import os
import sys

import pymongo


sys.path.insert(0, "D:/workplace/python/angr")
import utils
from CocoaPods.parser.parse_binary import binaries
import secret


def get_db_collecttions():
    client = pymongo.MongoClient("mongodb://%s:%s@code-analysis.org:%s" % (os.environ.get("MONGOUSER"), os.environ.get("MONGOPASS"), os.environ.get("MONGOPORT")))
    db = client["lib"]
    feature_string = db["feature_string"]
    feature_method = db["feature_method"]
    feature_lib = db["feature_lib"]
    return feature_string, feature_method, feature_lib


def get_value_by_len(data, length):
    if len(data) <= length:
        yield data
        return
    right = 0
    while len(data) - right >= length:
        yield data[right: right + length]
        right += length
    if right < len(data):
        yield data[right:]


def detect_by_simple(app_path, ida_path, tiny_parser, feature_string, feature_method, feature_lib, logger):
    try:
        parser = binaries(app_path, ida_path, tiny_parser, logger)
        method_signs, strings = parser.parse().get_result()
    except Exception as e:
        logger.error("An error occured in detect_by_simple, code_file: %s, error: %s", (app_path, e.args[0]))
        return
    print("find {} methods and {} strings".format(len(method_signs), len(strings)))
    hit_libraries = {}
    hit_methods = {}
    find_len = 500
    for method_sign in get_value_by_len(list(method_signs), length=find_len):
        for hit in feature_method.find({"method": {"$in": method_sign}}):
            print("hit method: ", hit)
            hit_methods[hit['method']] = hit["library"]
            for hit_lib in hit["library"]:

                if hit_lib["name"] not in hit_libraries:
                    hit_libraries[hit_lib["name"]] = {}
                if "method" not in hit_libraries[hit_lib["name"]]:
                    hit_libraries[hit_lib["name"]]['version'] = hit_lib['version']
                    hit_libraries[hit_lib["name"]]['method'] = []


    hit_strings = {}
    for string in get_value_by_len(list(strings), length=find_len):
        for hit in feature_string.find({"string": {"$in": string}}):
            print("hit string: ", hit)
            hit_strings[hit['string']] = hit["library"]
            for hit_lib in hit["library"]:
                if hit_lib["name"] not in hit_libraries:
                    hit_libraries[hit_lib["name"]] = {}
                if "string" not in hit_libraries[hit_lib["name"]]:
                    hit_libraries[hit_lib["name"]]['version'] = hit_lib['version']
                    hit_libraries[hit_lib["name"]]['string'] = []
                hit_libraries[hit_lib["name"]]["string"].append(hit['string'])

    return hit_libraries, hit_methods, hit_strings


def resort_libraries(hit_libraries, hit_methods, hit_strings):
    for method in hit_methods:
        if len(hit_libraries[method]):
            pass


def main(app_path, ida_path, tiny_parser, loglevel):
    logger = config_log(name=__name__, level=loglevel, log_path="./logs/{}.log".format(os.path.basename(__file__).replace(".py", "")))
    feature_string, feature_method, feature_lib = get_db_collecttions()
    hit_libraries, hit_methods, hit_strings = detect_by_simple(app_path, ida_path, tiny_parser, feature_string, feature_method, feature_lib, logger)
    resort_libraries(hit_libraries, hit_methods, hit_strings)
    hit = {"hit_libraries": hit_libraries, "hit_methods": hit_methods, "hit_strings": hit_strings}
    with open("hit_results.txt", "w") as f:
        json.dump(hit, f)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Detect the library in the specified app.')
    parser.add_argument('--app_path', help="the path of app that wants to be parsed.")
    parser.add_argument('--ida_path', help="the path of ida64. Help to parser the binaries files.")
    parser.add_argument('--tiny_parser', default=True, action='store_false', help="use the tiny parser to parser the binaries files.")
    parser.add_argument('--loglevel', default='INFO')
    args = parser.parse_args()
    main(args.app_path, args.ida_path, args.tiny_parser, args.loglevel)

