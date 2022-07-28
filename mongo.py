import os

import pymongo


def get_db_collecttions() -> tuple:
    """
    get the collections from the mongodb.
    :return: A tuple of collections. (lib_source_info, feature_string, feature_method, feature_lib)
    """
    client = pymongo.MongoClient("mongodb://%s:%s@code-analysis.org:%s" % (os.environ.get("MONGOUSER"), os.environ.get("MONGOPASS"), os.environ.get("MONGOPORT")))
    db = client["lib"]
    lib_source_info = db["lib_source_info"]
    feature_string = db["feature_string"]
    feature_method = db["feature_method"]
    feature_lib = db["feature_lib"]
    return lib_source_info, feature_string, feature_method, feature_lib


def update_library_lib(lib_name, lib_version, subspecs_name, method_signs, strings, global_vals):
    method_signs = list(set(method_signs))
    strings = list(set(strings))
    base_query = {"name": lib_name, "version": lib_version}
    if subspecs_name is not None:
        base_query.update({"subspecs_name": subspecs_name})
    for method_sign in method_signs:
        if len(list(global_vals.feature_lib.find({**base_query, "method": method_sign}))) > 0:
            continue
        global_vals.feature_lib.update_one(base_query, {'$push': {'method': method_sign}}, True)

    for string in strings:
        if len(list(global_vals.feature_lib.find({**base_query, "string": string}))) > 0:
            continue
        global_vals.feature_lib.update_one(base_query, {'$push': {'string': string}}, True)


def update_library_mtd(lib_name, lib_version, subspecs_name, method_signs, global_vals):
    method_signs = list(set(method_signs))
    lib_info = {"name": lib_name, "version": lib_version}
    if subspecs_name is not None:
        lib_info.update({"subspecs_name": subspecs_name})
    for method_sign in method_signs:
        if len(list(global_vals.feature_method.find({"method": method_sign, "library": lib_info}))) > 0:
            continue
        global_vals.feature_method.update_one({"method": method_sign}, {"$push": {"library": lib_info}}, True)


def update_library_str(lib_name, lib_version, subspecs_name, strings, global_vals):
    strings = list(set(strings))
    lib_info = {"name": lib_name, "version": lib_version}
    if subspecs_name is not None:
        lib_info.update({"subspecs_name": subspecs_name})
    for string in strings:
        if len(list(global_vals.feature_string.find({"string": string, "library": lib_info}))) > 0:
            continue
        global_vals.feature_string.update_one({"string": string}, {"$push": {"library": lib_info}}, True)
