import json
import os.path

import pymongo
import requests


# print and log
def pl(f, msg):
    print(msg)
    f.write(msg + "\n")


if not os.path.exists("./logs"):
    os.mkdir("./logs")
f = open("./logs/rank_lib_log.log", "w", encoding="utf-8")

client = pymongo.MongoClient("mongodb://lib:%s@code-analysis.org" % os.environ.get("MONGO"))
db = client["lib"]
collections = db["lib_rank_info"]

with open("./libs_info.json", "r", encoding="UTF-8") as f:
    libs_info = json.load(f)
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
        if repo.endswith("/"): repo = repo[:-1]
        ret = requests.get("https://api.github.com/repos/" + repo)
        if ret.status_code != 200:
            pl(f, "Error! ret.status_code is %s, git is %s." % (str(ret.status_code), git))
            continue
        ret = json.loads(ret.text)
        if "forks_count" not in ret or "stargazers_count" not in ret or "updated_at" not in ret or "watchers_count" not in ret:
            pl(f, "Error! git is %s, ret is %s." % (git, json.dumps(ret)))
            continue

        collections.insert_one(ret)
f.close()