import json
import os
cocoaPods_Specs = "./Specs"
libs_info = {}


def printDetails(msg, level=0):
    if level > -1:
        print(level, msg)


def find_specs(path, libs_info, level=0):
    if level <= 4:
        for sub_path in os.listdir(path):
            sub_path = os.path.join(path, sub_path)
            if os.path.isfile(sub_path):
                continue
            find_specs(sub_path, libs_info, level + 1)
        return

    for lib_resource in os.listdir(path):
        if not lib_resource.endswith('.podspec.json'):
            continue
        lib_resource = os.path.join(path, lib_resource)
        lib_info = None
        with open(lib_resource, "r", encoding="UTF-8") as f:
            lib_info = json.load(f)
        if lib_info is None:
            printDetails("parse json failed! filepath: %s" % lib_resource, 1)
            continue
        if "name" in lib_info and "version" in lib_info:
            lib_name = lib_info["name"]
            lib_version = str(lib_info["version"])
        else:
            sp = lib_resource.split(os.sep)
            lib_name = sp[-3]
            lib_version = sp[-2]
        printDetails("update! lib_name: %s, lib_version: %s." % (lib_name, lib_version), 0)
        libs_info.update({lib_name + ":" + lib_version: lib_info})



find_specs(cocoaPods_Specs, libs_info, level=0)
with open("./libs_info.json", "w", encoding="UTF-8") as f:
    json.dump(libs_info, f)
print("done!")


