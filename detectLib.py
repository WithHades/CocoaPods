import logging
import os

import pymongo

import utils
from ALibFileParser import parse


class global_var:
    file_path = None

    def __init__(self, logger, feature_string, feature_method, feature_lib):
        self.logger = logger
        self.feature_string = feature_string
        self.feature_method = feature_method
        self.feature_lib = feature_lib


def get_db_collecttions():
    client = pymongo.MongoClient("mongodb://%s:%s@code-analysis.org:%s" % (os.environ.get("MONGOUSER"), os.environ.get("MONGOPASS"), os.environ.get("MONGOPORT")))
    db = client["lib"]
    feature_string = db["feature_string"]
    feature_method = db["feature_method"]
    feature_lib = db["feature_lib"]
    return feature_string, feature_method, feature_lib


def detect_by_simple(app_path, global_vals):
    try:
        method_signs_dict, strings = parse(app_path)
    except Exception as e:
        global_vals.logger.error("An error occured in detect_by_simple, code_file: %s, error: %s", (app_path, e.args[0]))
        return
    method_signs = []
    for key in method_signs_dict:
        method_signs = list(set(method_signs).union(set(method_signs_dict[key])))
    hit_libraries = {}
    hit_methods = {}
    for method_sign in method_signs:
        for hit in global_vals.feature_method.find({"method": method_sign}):
            hit_methods[hit['method']] = hit["library"]
            hit_libraries[hit["library"]] = {}
            hit_libraries[hit["library"]]["methods"] = hit['method']

    hit_strings = {}
    for string in strings:
        for hit in global_vals.feature_string.find({"string": string}):
            hit_strings[hit['string']] = hit["string"]
            hit_libraries[hit["library"]] = {}
            hit_libraries[hit["library"]]["strings"] = hit['string']


def main():
    logger = utils.config_log(name=__name__, level=logging.INFO, log_path="./logs/{}.log".format(os.path.basename(__file__).replace(".py", "")))
    feature_string, feature_method, feature_lib = get_db_collecttions()
    global_vals = global_var(logger, feature_string, feature_method, feature_lib)
    detect_by_simple(app_path, global_vals)

