import json
import os
import re
import subprocess
import sys

import chardet
import pymongo

import logging

import utils


def traverse(json_data):
    method_signs = []
    strings = []
    if "kind" in json_data:
        kind = json_data["kind"]
        if kind == "ObjCMethodDecl":
            if "mangledName" in json_data:
                method_signs.append(json_data["mangledName"])
        if kind == "StringLiteral":
            if "value" in json_data:
                string = json_data["value"][1:-1]
                if len(string) != 0 and len(string) % 4 == 0:
                    model = re.findall("\d{3}", string)
                    if len(model) == int(len(string) / 4):
                        bytes = b''
                        for c in model:
                            bytes += int.to_bytes(int(c, 8), length=1, byteorder='little')
                        string = str(bytes, chardet.detect(bytes).get('encoding'))
                strings.append(string)
            return method_signs, strings
    if "inner" in json_data:
        for inner in json_data["inner"]:
            ret_method_signs, ret_strings = traverse(inner)
            method_signs = list(set(method_signs).union(set(ret_method_signs)))
            strings = list(set(strings).union(set(ret_strings)))
    return method_signs, strings


logger = utils.config_log(name=__name__, level=logging.INFO, log_path="./logs/parse_oc.log")

client = pymongo.MongoClient("mongodb://%s:%s@code-analysis.org:%s" % (os.environ.get("MONGOUSER"), os.environ.get("MONGOPASS"), os.environ.get("MONGOPORT")))
db = client["lib"]
collections = db["lib_source_info"]

feature_string = db["feature_string"]
feature_method = db["feature_method"]
# 理论上只需要前面两张表就好了，测试阶段多添加一个表格
feature_lib = db["feature_lib"]

lib_path = "../libraries"
if not os.path.exists(lib_path):
    exit(0)

if len(sys.argv) < 1:
    print("please input compiler!")
    exit(0)

compiler = sys.argv[1]

os.chdir(lib_path)
cwd_path = os.getcwd()
for path in os.listdir(cwd_path):
    file_path = os.path.join(cwd_path, path)
    if os.path.isfile(file_path) or not os.listdir(file_path):
        continue
    lib_name = path[:path.rfind("_")]
    lib_version = path[path.rfind("_") + 1:]
    ret = collections.find_one({"name": lib_name, "version": lib_version})
    if not ret:
        logger.error("ERROR: Could not find library in database! file_path: %s" % file_path)
        continue
    if "source_files" not in ret:
        logger.error("ERROR: Could not find source_files field in library info! file_path: %s" % file_path)
        continue
    if isinstance(ret["source_files"], list):
        logger.error("ERROR: source_files is a list! file_path: %s" % file_path)
        continue
    source_files = ret["source_files"]
    if source_files.endswith("*"):
        logger.info("Can not identify source_files type! file_path: %s" % file_path)
        continue
    if source_files.endswith(".swift") or source_files.endswith(".{swift}"):
        logger.info("Guess source_files maybe using swift! file_path: %s" % file_path)
        continue
    if source_files.endswith(".h"):
        logger.info("Maybe it is a (xc)framework! file_path: %s" % file_path)
        continue
    if not (source_files.endswith(".m") or source_files.endswith("{h,m}") or source_files.endswith("{m,h}")):
        logger.error("Can not identify source_files type!!! file_path: %s" % file_path)
        continue
    if "*" not in source_files:
        logger.error("maybe the lib has one oc file? file_path: %s" % file_path)
        continue
    source_path = os.path.join(file_path, source_files[:source_files.find("*")])
    for root, dirs, files in os.walk(source_path):
        for file in files:
            if not file.endswith(".m") and not file.endswith(".h"):
                continue
            file_full_path = os.path.join(root, file)
            try:
                with open(file_full_path, "r", encoding="UTF-8") as f:
                    code = f.read()
            except UnicodeDecodeError as e:
                try:
                    with open(file_full_path, "r", encoding="gbk") as f:
                        code = f.read()
                except Exception as e:
                    logger.error("decode error. file_path: %s" % file_full_path)
                    continue
            '''
            code = re.sub(r"(^ *# *(import|include))", "//\\1", code, flags=re.M)
            with open(tmp, "w", encoding="UTF-8") as f:
                f.write(code)
            tmp = file_full_path + ".tmp"
            cmd = "clang -fsyntax-only -ferror-limit=0 -Xclang -ast-dump=json {} >> ast_result.txt".format(tmp)
            '''
            cmd = compiler + " -fsyntax-only -ferror-limit=0 -Xclang -ast-dump=json {} >> ast_result.txt".format(file_full_path)
            subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE).wait()
            if not os.path.exists("ast_result.txt"):
                logger.error("Could not generate ast. file_path: %s" % file_full_path)
                continue
            with open("ast_result.txt", "r", encoding="UTF-8") as f:
                data = f.read()
                data_len = f.seek(0, 2) - f.seek(0)
            if "StringLiteral" not in data and "ObjCMethodDecl" not in data:
                logger.error("Could not generate ast. file_path: %s" % file_full_path)
                continue
            start = 0
            end = data_len
            method_signs = []
            strings = []
            while start < end:
                try:
                    ast = json.loads(data[start:end])
                    ret_method_signs, ret_strings = traverse(ast)
                    method_signs = list(set(method_signs).union(set(ret_method_signs)))
                    strings = list(set(strings).union(set(ret_strings)))
                    start = end
                    end = data_len
                except json.decoder.JSONDecodeError as err:
                    if err.msg == 'Extra data':
                        end = start + err.pos
                    else:
                        logger.error("Could not generate ast. file_path: %s" % file_full_path)
                        logger.error(err.msg)
                        break
            # update feature_lib
            for method_sign in method_signs:
                if len(list(feature_lib.find({"name": lib_name, "version": lib_version, "method": method_sign}))) > 0:
                    continue
                feature_lib.update_one({"name": lib_name, "version": lib_version}, {'$push': {'method': method_sign}}, True)
            for string in strings:
                if len(list(feature_lib.find({"name": lib_name, "version": lib_version, "string": string}))) > 0:
                    continue
                feature_lib.update_one({"name": lib_name, "version": lib_version}, {'$push': {'string': string}}, True)

            # update feature_method & feature_string
            lib_info = {"name": lib_name, "version": lib_version}
            for method_sign in method_signs:
                if len(list(feature_method.find({"method": method_sign, "library": lib_info}))) > 0:
                    continue
                feature_method.update_one({"method": method_sign}, {"$push": {"library": lib_info}}, True)
            for string in strings:
                if len(list(feature_string.find({"string": string, "library": lib_info}))) > 0:
                    continue
                feature_string.update_one({"string": string}, {"$push": {"library": lib_info}}, True)
            os.remove("ast_result.txt")

        ''' 
            if code.count("@implementation ") > 1 or code.count("@implementation ") <= 0 :
                logger.error("Could not find implementation or find multiple implementations! file_path: %s" % file)
                continue
            ret = re.findall(r"[\+-] ?\([\w\* ]+\)[\s\S]*?\{", code)
            for method in ret:
                # - (NSInteger)numberOfComponentsInPickerView:(UIPickerView *)pickerView {
                # - (void)pickerView:(UIPickerView *)pickerView didSelectRow:(NSInteger)row inComponent:(NSInteger)component
                # {
                pass
            '''







