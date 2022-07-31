import json
import os
import shutil
import subprocess

from .tiny_parser import libParser
from .base_logger import logger_


class binaries(logger_):

    def __init__(self, binary_file: str, ida_path: str = None, tiny_parser: bool = True, logger=None):
        super().__init__(logger)
        self._binary_file = binary_file
        self._ida_path = ida_path
        self._tiny_parser = tiny_parser
        self._method_signs = set()
        self._strings = set()


    def parse_by_ida(self) -> None:
        """
        parse the binary file by ida.
        :return:
        """
        tmp_path = "./tmp"
        if not os.path.exists(tmp_path):
            os.mkdir(tmp_path)

        parser = libParser(self._binary_file, tmp_path)
        for path in parser.parse().get_result():
            script_path = os.path.join(os.path.dirname(__file__), "ida_script.py")
            cmd = self._ida_path + f' -A -S"{script_path}" ' + path
            try:
                subprocess.Popen(cmd).wait()
            except Exception as e:
                self._logger.error("An error occured in parse_by_ida, 0x1cmd is %s, code_file is %s, msg: %s" % (cmd, self._binary_file, e.args[0]))
                continue
            if not os.path.exists("result.txt"):
                self._logger.error("An error occured in parse_by_ida, 0x2cmd is %s, code_file is %s" % (cmd, self._binary_file))
                continue
            with open("result.txt", "w") as f:
                data = json.load(f)
            os.remove("result.txt")
            ret_method_signs, ret_strings = set(data[0]), set(data[1])
            self._method_signs = self._method_signs.union(ret_method_signs)
            self._strings = self._strings.union(ret_strings)
        shutil.rmtree(tmp_path)


    def parse_by_tiny(self) -> None:
        """
        parse the binary file by tiny parser.
        :return:
        """
        parser = libParser(self._binary_file)
        class_infos, strings = parser.parse().get_result()
        for key in class_infos:
            self._method_signs = self._method_signs.union(set(class_infos[key]))
        self._strings = self._strings.union(set(strings))


    def parse(self):
        """
        if the ida path is not None, parsed by ida, else parsed by tiny parser.
        :return:
        """
        if self._ida_path is not None:
            self.parse_by_ida()
        if self._tiny_parser:
            self.parse_by_tiny()
        return self


    def get_result(self) -> (set, set):
        return self._method_signs, self._strings
