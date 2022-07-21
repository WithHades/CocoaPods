import json
import os

import pymongo

client = pymongo.MongoClient("mongodb://lib:%s@code-analysis.org" % os.environ.get("MONGO"))
db = client["lib"]
collections = db["lib_source_info"]

with open("./libs_info.json", "r", encoding="UTF-8") as f_:
    libs_info = json.load(f_)
    for lib_name in libs_info:
        for lib_version in list(libs_info[lib_name].keys()):
            lib_info = libs_info[lib_name][lib_version]
            collections.update_one(lib_info, {"$set": lib_info}, True)

