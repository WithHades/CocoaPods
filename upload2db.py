import json
import os

import pymongo

client = pymongo.MongoClient("mongodb://%s:%s@code-analysis.org:%s" % (os.environ.get("MONGOUSER"), os.environ.get("MONGOPASS"), os.environ.get("MONGOPORT")))
db = client["lib"]
collections = db["lib_source_info"]

with open("./libs_info.json", "r", encoding="UTF-8") as f_:
    libs_info = json.load(f_)
    for lib_name in libs_info:
        for lib_version in list(libs_info[lib_name].keys()):
            lib_info = libs_info[lib_name][lib_version]
            try:
                lib_info = json.loads(json.dumps(lib_info).replace("${", "_{"))
                ret = collections.update_one(lib_info, {"$set": lib_info}, True)
            except Exception as e:
                print(e)
                print(lib_info)

