import json
import os.path
from time import sleep

import pymongo
import requests


# print and log
def pl(f, msg):
    print(msg)
    f.write(msg + "\n")


if not os.path.exists("./logs"):
    os.mkdir("./logs")
f = open("./logs/rank_lib_log.log", "w+", encoding="utf-8")

client = pymongo.MongoClient("mongodb://%s:%s@code-analysis.org:%s" % (os.environ.get("MONGOUSER"), os.environ.get("MONGOPASS"), os.environ.get("MONGOPORT")))
db = client["lib"]
collections = db["lib_rank_info"]

with open("./libs_info.json", "r", encoding="UTF-8") as f_:
    libs_info = json.load(f_)
    for lib_name in libs_info:
        # in most cases, the last one is the latest version
        lib_version = list(libs_info[lib_name].keys())[-1]
        lib_info = libs_info[lib_name][lib_version]
        if "source" not in lib_info or "git" not in lib_info["source"]:
            continue
        git = lib_info["source"]["git"]
        if "github" not in git:
            continue
        repo = git[git.find("github.com") + len("github.com"):].replace(".git", "")
        lenx = len(list(collections.find({"full_name": repo[1:]})))
        if lenx > 0:
            collections.update_one(ret, {"$set": {"lib_name": lib_name, "lib_version": lib_version}}, True)
            continue
        if repo.endswith("/"): repo = repo[:-1]
        ret = requests.get("https://api.github.com/repos" + repo, auth=('244036962@qq.com', os.environ.get("GITTOKEN")))
        if ret.status_code != 200:
            pl(f, "Error! ret.status_code is {}, ret.headers is {}, git is {}.".format(ret.status_code, ret.headers, git))
            continue
        ret = json.loads(ret.text)
        if "forks_count" not in ret or "stargazers_count" not in ret or "updated_at" not in ret or "watchers_count" not in ret:
            pl(f, "Error! git is {}, ret is {}.".format(git, json.dumps(ret)))
            continue
        ret.update({"lib_name": lib_name, "lib_version": lib_version})
        collections.update_one(ret, {"$set": ret}, True)
        sleep(0.8)

f.close()