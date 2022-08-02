import argparse
import json
import os
import re

import logging

import utils

from mongo import mongodb

from parser.base_logger import logger_
from parser.parse_oc import clang, libclang
from parser.parse_binary import binaries


class global_var:
    file_path = None

    def __init__(self, logger, lib_source_info, feature_string, feature_method, feature_lib, compiler, libclang,
                 ida_path):
        self.logger = logger
        self.lib_source_info = lib_source_info
        self.feature_string = feature_string
        self.feature_method = feature_method
        self.feature_lib = feature_lib
        self.compiler = compiler
        self.libclang = libclang
        self.ida_path = ida_path


class feature_extract(logger_):
    def __init__(self, lib_name: str, lib_version: str, file_path: str, mongo, ida_path: str = None,
                 compiler: str = None, libclang: str = None, tiny_parser: bool = True, logger=None):
        super().__init__(logger)
        self._lib_name = lib_name
        self._lib_version = lib_version
        self._file_path = file_path
        self._mongo = mongo
        self._ida_path = ida_path
        self._libclang = libclang
        self._compiler = compiler
        self._tiny_parser = tiny_parser
        self._method_signs = set()
        self._strings = set()


    @staticmethod
    def get_regex(source):
        if "**" in source:
            source = source[:source.find("**")] + "**" + source[source.find("**") + 2:].replace("/", "/?")
        regex = source.replace("*", "_").replace(".", r"\.").replace("__", r".*?").replace("_", r".*?")
        regex = regex.replace("{", r"[").replace("}", r"]")
        regex = regex.replace(",", "").replace(" ", "")
        return regex

    def parse_code_file(self, code_file: str) -> None:
        """
        parse the source file and update the methods and strings to the mongo.
        :param code_file: source code file.
        :return:
        """
        method_signs, strings = set(), set()
        # parse the c/c++/objective-c files
        if code_file.endswith(".h") or code_file.endswith(".m")  or code_file.endswith(".mm") or code_file.endswith(".c") or code_file.endswith(".cpp"):
            if self._libclang is not None:
                self._logger.debug("using libclang to parse code file, code_file: %s" % code_file)
                parser = libclang(code_file, self._libclang, self._logger)
                method_signs, strings = parser.parse().get_result()
                self._logger.debug("find {} methods and {} strings in {}.".format(len(method_signs), len(strings), str(code_file)))
                self._method_signs = self._method_signs.union(method_signs)
                self._strings = self._strings.union(strings)
            if self._compiler is not None:
                self._logger.debug("using clang to parse code file, code_file: %s" % code_file)
                parser = clang(code_file, self._compiler, self._logger)
                method_signs, strings = parser.parse().get_result()
                self._logger.debug("find {} methods and {} strings in {}.".format(len(method_signs), len(strings), str(code_file)))
                self._method_signs = self._method_signs.union(method_signs)
                self._strings = self._strings.union(strings)


    def parse_code_files(self, source_files: [str, list]) -> None:
        """
        filters the code files depending on the field of source_files.
        then parse the code files and update the methods and strings.
        :param source_files: field of source files
        :return: None
        """
        if isinstance(source_files, str):
            source_files = [source_files]
        for source_file in source_files:
            self._logger.debug("processing source_file: %s" % str(source_file))
            source_file_re = self.get_regex(source_file)
            self._logger.debug("source_file_re: %s, source_file: %s, file_path: %s" % (source_file_re, source_file, self._file_path))
            for root, dirs, files in os.walk(self._file_path):
                for file in files:
                    code_file = os.path.join(root, file)
                    try:
                        if len(re.findall(source_file_re, code_file)) <= 0:
                            continue
                    except Exception as e:
                        self._logger.error("regex is wrong! source_file_re: %s, code_file: %s" % (source_file_re, code_file))
                        continue
                    self.parse_code_file(code_file)


    def parse_binary(self, code_file: str) -> None:
        """
        parse the binary file. such as fat files that contains one or more than arch and obj files and macho files.
        :param code_file: path to the binary file.
        :return:
        """
        try:
            self._logger.debug("processing binary: %s" % str(code_file))
            parser = binaries(code_file, self._ida_path, self._tiny_parser, self._logger)
            ret_method_signs, ret_strings = parser.parse().get_result()
            self._logger.debug("find {} methods and {} strings in {}.".format(len(ret_method_signs), len(ret_strings), str(code_file)))
            self._method_signs = self._method_signs.union(ret_method_signs)
            self._strings = self._strings.union(ret_strings)
        except Exception as e:
            self._logger.error("An error occured in parse_binary, code_file: %s, error: %s", (code_file, e.args[0]))


    def parse_libraries(self, vendored_libraries: [str, list]) -> None:
        """
        filters the code files depending on the field of vendored_libraries.
        then parse the code files and update the methods and strings.
        :param vendored_libraries:
        :return:
        """
        if isinstance(vendored_libraries, str):
            vendored_libraries = [vendored_libraries]
        for vendored_library in vendored_libraries:
            self._logger.debug("processing vendored_library: %s" % str(vendored_library))
            vendored_library_re = self.get_regex(vendored_library)
            for root, dirs, files in os.walk(self._file_path):
                for file in files:
                    code_file = os.path.join(root, file)
                    try:
                        if len(re.findall(vendored_library_re, code_file)) <= 0: continue
                    except Exception as e:
                        self._logger.error("regex is wrong! source_file_re: %s, code_file: %s" % (vendored_library_re, code_file))
                        continue
                    if not code_file.endswith(".a"):
                        continue

                    self.parse_binary(code_file)


    def parse_framework(self, vendored_frameworks: [str, list]) -> None:
        """
        filters the code files depending on the field of vendored_frameworks.
        then parse the code files and update the methods and strings.
        :param vendored_frameworks:
        :return:
        """
        if isinstance(vendored_frameworks, str):
            vendored_frameworks = [vendored_frameworks]
        for vendored_framework in vendored_frameworks:
            self._logger.debug("processing vendored_framework: %s" % str(vendored_framework))
            vendored_framework_re = self.get_regex(vendored_framework)
            for root, dirs, files in os.walk(self._file_path):
                for file in files:
                    code_file = os.path.join(root, file)
                    try:
                        if len(re.findall(vendored_framework_re, root)) <= 0: continue
                    except Exception as e:
                        self._logger.error("regex is wrong! parse_framework: %s, code_file: %s" % (vendored_framework_re, code_file))
                        continue
                    if ".framework" not in code_file and ".xcframework" not in code_file:
                        continue
                    idx = code_file.find(".framework") if code_file.find(".framework") != -1 else code_file.find(".xcframework")
                    framework_name = code_file[code_file.find("/") + 1: idx]
                    if framework_name != file: continue

                    self.parse_binary(code_file)


    def update_to_mongodb(self, subspecs_name) -> None:
        """
        update the current method signatures and strings to mongodb.
        :param subspecs_name:
        :return:
        """
        self._mongo.set_lib(self._lib_name, self._lib_version, subspecs_name)
        self._mongo.update_all(self._method_signs, self._strings)
        self._method_signs, self._strings = set(), set()


    def parse_source_info(self, source_info: dict, subspecs_name=None):
        """
        parse the source information and update the method signatures and string to mongodb.
        :param source_info:
        :param subspecs_name:
        :return:
        """
        if "source_files" in source_info:
            self.parse_code_files(source_info["source_files"])
        if "vendored_frameworks" in source_info:
            self.parse_framework(source_info["vendored_frameworks"])
        if "vendored_libraries" in source_info:
            self.parse_libraries(source_info["vendored_libraries"])

        self.update_to_mongodb(subspecs_name)

        if "subspecs" in source_info:
            for subspec in source_info["subspecs"]:
                space_name = subspec["name"] if "name" in subspec else "unknown"
                self.parse_source_info(subspec, space_name)
        for key in source_info:
            if isinstance(source_info[key], dict):
                self.parse_source_info(source_info[key], subspecs_name)


def main(compiler, libclang, ida_path, tiny_parser, drop, loglevel):
    lib_path = "../libraries"
    if not os.path.exists(lib_path):
        return

    logger = utils.config_log(name=__name__, level=loglevel, log_path="./logs/{}.log".format(os.path.basename(__file__).replace(".py", "")))

    mongo = mongodb()
    if drop:
        mongo.drop()

    os.chdir(lib_path)
    cwd_path = os.getcwd()
    for path in os.listdir(cwd_path):
        file_path = os.path.join(cwd_path, path)
        if os.path.isfile(file_path) or not os.listdir(file_path):
            continue

        lib_name = path[:path.rfind("_")]
        lib_version = path[path.rfind("_") + 1:]
        ret = mongo.find_source_info(lib_name, lib_version)
        if not ret:
            logger.error("Could not find library in database! file_path: %s" % file_path)
            continue
        logger.debug("processing library: %s, version: %s" % (lib_name, lib_version))
        try:
            fe = feature_extract(lib_name=lib_name, lib_version=lib_version, file_path=file_path, mongo=mongo,
                                 ida_path=ida_path, compiler=compiler, libclang=libclang, tiny_parser=tiny_parser, logger=logger)
            fe.parse_source_info(ret)
        except Exception as e:
            logger.error("A error occured! msg: " + e.args[0])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='The parser for libraries.')
    parser.add_argument('--compiler', help="the path of clang compiler. Help to parser the c/oc files.")
    parser.add_argument('--libclang', help="the path of libclang.so. Help to parser the c/oc files.")
    parser.add_argument('--ida_path', help="the path of ida64. Help to parser the binaries files.")
    parser.add_argument('--tiny_parser', default=True, action='store_false', help="use the tiny parser to parser the binaries files.")
    parser.add_argument('--drop', default=False, action='store_true', help="Does drop the clooections of feature_method, feature_string and feature_lib.")
    parser.add_argument('--loglevel', default='INFO')
    args = parser.parse_args()
    main(args.compiler, args.libclang, args.ida_path, args.tiny_parser, args.drop, args.loglevel)
