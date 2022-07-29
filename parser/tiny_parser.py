import math
import os.path

from .base_logger import logger_

ERROR_CODE = -1
CPU_TYPES = {-1: "CPU_TYPE_ANY",
             1: "CPU_TYPE_VAX",
             6: "CPU_TYPE_MC680x0",
             7: "CPU_TYPE_I386",
             0x01000000 | 7: "CPU_TYPE_X86_64",
             0xA: "CPU_TYPE_MC98000",
             0xB: "CPU_TYPE_HPPA",
             0xC: "CPU_TYPE_ARM",
             0x01000000 | 0xC: "CPU_TYPE_ARM64",
             0xD: "CPU_TYPE_MC88000",
             0xE: "CPU_TYPE_SPARC",
             0xF: "CPU_TYPE_I860",
             0x10: "CPU_TYPE_ALPHA",
             0x12: "CPU_TYPE_POWERPC",
             0x01000000 | 0x12: "CPU_TYPE_POWERPC64"
             }
FILE_TYPES = {1: "OBJECT",
              2: "EXCUTABLE",
              4: "CORE",
              6: "DYLIB",
              7: "DYLINKER",
              8: "BUNDLE",
              10: "DSYM",
              11: "KEXT_BUNDLE"}


class LCName:
    LC_SEGEMENT = 0x01
    LC_SEGMENT_64 = 0X19
    LC_LOAD_DYLINKER = 0x0E
    LC_UUID = 0x1B
    LC_THREAD = 0x04
    LC_UNIXTHREAD = 0x05
    LC_CODE_SIGNATURE = 0x1D
    LC_ENCRPTION_INFO = 0x21
    LC_SYMTAB = 0x2


class baseParser(logger_):
    def __init__(self, f=None, logger=None):
        super().__init__(logger)
        self._f = f

    def _read_string(self, offset: int = None) -> str:
        """
        read a string encoded by utf-8 from the given offset.
        if offset is None, then from the current position.
        :param offset: the position that wants to read a string.
        :return: string encoded by utf-8.
        """
        now_offset = self._f.tell()
        if offset is not None:
            self._f.seek(offset)
        symbol = b"\x01"
        while symbol[-1] != 0:
            symbol += self._f.read(1)
        if offset is not None:
            self._f.seek(now_offset)
        try:
            symbol = symbol[1:-1].decode(encoding="utf-8", errors="ignore")
        except:
            error = offset if offset is not None else now_offset
            self._logger.error("trying to decode(utf-8) str failed. offset:%s, hex: %s" % (hex(error), symbol.hex()))
            symbol = ""
        return symbol


    def _read_ustring(self) -> str:
        """
        read a string encoded by utf-16le.
        :return: string encoded by utf-16le.
        """
        symbol = b"\x01\x01"
        while symbol[-1] != 0 or symbol[-2] != 0:
            symbol += self._f.read(2)
        return symbol[2:-2].decode(encoding="UTF-16LE")


    @staticmethod
    def _read_string_from_bytes(trans_bytes: bytes) -> str:
        """
        read a string from the bytes that has a fixed length.
        :param trans_bytes:
        :return: string
        """
        index = trans_bytes.find(b"\x00")
        if index != -1:
            trans_bytes = trans_bytes[:index]
        return trans_bytes.decode("utf-8")


class libParser_(baseParser):

    def __init__(self, f, binary_file, logger=None):
        super().__init__(f, logger)
        self._binary_file = binary_file

        self._macho_offset = self._f.tell()
        self._arch = 32
        # the length of the addr.
        self._var_len = 4
        self._byteorder = "little"
        self._segments = {}
        self._symbols = []
        # relocation table.
        self._relo_table = {}

        # contains method signatures and strings of methods
        self._class_infos = {}
        self._strings = set()


    def _relocation_translate(self) -> int:
        """
        read a addr from the current position.
        auto translate the addr to actual addr if it in the relo_table.
        :return: actural addr.
        """
        if self._f.tell() in self._relo_table:
            ret = self._relo_table[self._f.tell()]
            self._f.read(self._var_len)
            return ret
        else:
            return int.from_bytes(self._f.read(self._var_len), byteorder=self._byteorder)


    def _parse_class(self, class_offset: int, methType: str) -> None:
        """
        parse a class and update a list of all its method signature to class infos.
        :param class_offset: the offset of the class that wants to be parsed.
        :param methType: class method or instance method.
        """

        offet = self._f.tell()

        # parser class struct
        self._f.seek(self._macho_offset + class_offset)
        isa_vm = self._relocation_translate()
        if isa_vm != 0:
            isa_offset = isa_vm - self._segments["__DATA"]["__objc_data"]["addr"] + self._segments["__DATA"]["__objc_data"]["offset"]
            if isa_offset == class_offset:
                return
            self._parse_class(isa_offset, methType="+")

        self._f.read(self._var_len * 3)  # skip superclass/cache/vtable

        # the offset of class data
        cls_data_offset_vm = self._relocation_translate()
        if cls_data_offset_vm % self._var_len != 0:
            cls_data_offset_vm = math.floor(cls_data_offset_vm / self._var_len) * self._var_len
        cls_data_offset = cls_data_offset_vm - self._segments["__DATA"]["__objc_const"]["addr"] + self._segments["__DATA"]["__objc_const"]["offset"]

        # goto the offset of class data and parser class info
        self._f.seek(self._macho_offset + cls_data_offset)

        # for 32-bits, skip flags/instanceStart/instanceSize/ivarLayout
        # for 64-bits, skip flags/instanceStart/instanceSize/reserved/ivarLayout
        self._f.read(self._var_len * 4) if self._var_len == 4 else self._f.read(4 * 4 + self._var_len)

        class_name_offset_vm = self._relocation_translate()
        base_methods_offset_vm = self._relocation_translate()
        if base_methods_offset_vm == 0:
            # class doesn't have the method of methType
            self._f.seek(offet)
            return
        base_methods_offset = base_methods_offset_vm - self._segments["__DATA"]["__objc_const"]["addr"] + self._segments["__DATA"]["__objc_const"]["offset"]

        # parse the class name.
        if "__objc_classname" in self._segments["__TEXT"]:
            class_name_offset = class_name_offset_vm - self._segments["__TEXT"]["__objc_classname"]["addr"] + self._segments["__TEXT"]["__objc_classname"]["offset"]
        else:
            class_name_offset = class_name_offset_vm
        self._f.seek(self._macho_offset + class_name_offset)
        class_name = self._read_string()
        self._class_infos[class_name] = []

        # parser base methods
        self._f.seek(self._macho_offset + base_methods_offset)
        entsize = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
        count = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
        for _ in range(count):
            method_name = self._relocation_translate()
            method_types = self._relocation_translate()
            method_imp = self._relocation_translate()
            method_name = method_name - self._segments["__TEXT"]["__objc_methname"]["addr"] + self._segments["__TEXT"]["__objc_methname"]["offset"]
            method_name = self._read_string(offset=self._macho_offset + method_name)
            self._class_infos[class_name].append(methType + "[" + class_name + " " + method_name + "]")

        self._f.seek(offet)


    def _parse_class_from_section(self, section_name: str) -> None:
        """
        read the class information from the specific section.
        and update a list of all its method signature to class infos.
        :param section_name: the section that wants to parse the class information.
        """
        if "__DATA" not in self._segments or section_name not in self._segments["__DATA"]:
            return
        if "__DATA" not in self._segments or "__objc_data" not in self._segments["__DATA"] or "__objc_const" not in self._segments["__DATA"]:
            self._logger.error("Could not find __DATA or __DATA['__objc_data']! binary file: %s" % self._binary_file)
            return
        if "__TEXT" not in self._segments or "__objc_methname" not in self._segments["__TEXT"]:
            self._logger.error("Could not find __TEXT or __TEXT['__objc_methname']! binary file: %s" % self._binary_file)
            return
        # handle class and method
        self._f.seek(self._macho_offset + self._segments["__DATA"][section_name]["offset"])
        class_num = int(self._segments["__DATA"][section_name]["size"] / self._var_len)
        for _ in range(class_num):
            class_item_vm = self._relocation_translate()
            class_offset = class_item_vm - self._segments["__DATA"]["__objc_data"]["addr"] + self._segments["__DATA"]["__objc_data"]["offset"]
            self._parse_class(class_offset, methType="-")



    def _parse_string_from_section(self, section_name: str, read_func) -> None:
        """
        read strings from sections and update to strings.
        :param section_name: section name of wants to read strings.
        :param read_func: the read function.
        :return: None
        """
        if "__TEXT" not in self._segments or section_name not in self._segments["__TEXT"]:
            return

        self._f.seek(self._macho_offset + self._segments["__TEXT"][section_name]["offset"])
        while self._f.tell() < self._macho_offset + self._segments["__TEXT"][section_name]["offset"] + self._segments["__TEXT"][section_name]["size"]:
            self._strings.add(read_func())


    def _parse_segments(self) -> None:
        """
        parse the segments info of a macho file and update to the segments.
        """

        '''
        lc_segment_name = self.f.read(16).decode("utf-8")
        lc_vm_addr = int.from_bytes(self.f.read(self.var_len), byteorder=self.byteorder)
        lc_vm_size = int.from_bytes(self.f.read(self.var_len), byteorder=self.byteorder)
        lc_file_offset = int.from_bytes(self.f.read(self.var_len), byteorder=self.byteorder)
        lc_file_size = int.from_bytes(self.f.read(self.var_len), byteorder=self.byteorder)
        lc_max_pro = int.from_bytes(self.f.read(4), byteorder=self.byteorder)
        lc_init_pro = int.from_bytes(self.f.read(4), byteorder=self.byteorder)
        '''
        self._f.read(16 + self._var_len * 4 + 4 + 4)

        lc_sec_num = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
        lc_flag = int.from_bytes(self._f.read(4), byteorder=self._byteorder)

        # parser section info
        for _ in range(lc_sec_num):
            section_name = self._read_string_from_bytes(self._f.read(16))
            segment_name = self._read_string_from_bytes(self._f.read(16))
            if segment_name not in self._segments:
                self._segments[segment_name] = {}
            self._segments[segment_name][section_name] = {}
            self._segments[segment_name][section_name]["addr"] = int.from_bytes(self._f.read(self._var_len), byteorder=self._byteorder)
            self._segments[segment_name][section_name]["size"] = int.from_bytes(self._f.read(self._var_len), byteorder=self._byteorder)
            self._segments[segment_name][section_name]["offset"] = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
            self._segments[segment_name][section_name]["align"] = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
            self._segments[segment_name][section_name]["relo_offset"] = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
            self._segments[segment_name][section_name]["relo_num"] = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
            self._segments[segment_name][section_name]["flags"] = int.from_bytes(self._f.read(4), byteorder=self._byteorder)

            # reserve
            self._f.read(8)
            if self._arch == 64:
                self._f.read(4)


    def _parse_symtab(self) -> None:
        """
        parse the symbol table info of macho file and update to the symbols.
        """
        symbol_table_offset = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
        symbol_table_number = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
        string_table_offset = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
        string_table_size = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
        _offset = self._f.tell()
        self._f.seek(self._macho_offset + symbol_table_offset)
        for symbol in range(symbol_table_number):
            string_table_index = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
            symbol_type = int.from_bytes(self._f.read(1), byteorder=self._byteorder)
            symbol_section_index = int.from_bytes(self._f.read(1), byteorder=self._byteorder)
            symbol_description = int.from_bytes(self._f.read(2), byteorder=self._byteorder)
            symbol_value = int.from_bytes(self._f.read(self._var_len), byteorder=self._byteorder)
            self._symbols.append([string_table_index, symbol_type, symbol_section_index, symbol_description, symbol_value])
        self._f.seek(_offset)



    def _parse_load_commands(self, lc_num: int) -> None:
        """
        parse the load commands and update the segments and symbols information.
        :param lc_num: the count of load commands
        """
        for _ in range(lc_num):
            lc_cmd = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
            lc_cmd_size = int.from_bytes(self._f.read(4), byteorder=self._byteorder)

            # parser self.segments info
            if lc_cmd == LCName.LC_SEGMENT_64 or lc_cmd == LCName.LC_SEGEMENT:
                self._parse_segments()
            elif lc_cmd == LCName.LC_SYMTAB:
                self._parse_symtab()
            else:
                self._f.read(lc_cmd_size - 8)


    def _parse_relocation_table(self) -> None:
        """
        parse relocation informations of each section and update to the relo_table.
        """
        for segment in self._segments:
            for section in self._segments[segment]:
                section = self._segments[segment][section]
                section_offset = section["offset"]
                relo_offset = section["relo_offset"]
                relo_num = section["relo_num"]
                self._f.seek(self._macho_offset + relo_offset)
                for relo in range(relo_num):
                    addr = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
                    re_addr = section_offset + addr
                    symbol_index = int.from_bytes(self._f.read(3), byteorder=self._byteorder)
                    flag = int.from_bytes(self._f.read(1), byteorder=self._byteorder)
                    r_type = (flag & 0xF0) >> 4
                    r_extern = (flag & 0x8) >> 3
                    r_pcrel = (flag & 0x4) >> 2
                    r_length = flag & 0x3
                    if r_extern != 1:
                        continue
                    symbol_value = self._symbols[symbol_index][4]
                    self._relo_table[self._macho_offset + re_addr] = symbol_value


    def parse_mach(self):
        """
        parse a macho file
        """

        # parser macho header
        magic = self._f.read(4)[::-1].hex()
        if magic == "feedface":
            self._arch = 32
        elif magic == "feedfacf":
            self._arch = 64
        else:
            return self
        self._var_len = 4 if self._arch == 32 else 8
        CPU_type = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
        CPU_type = CPU_TYPES[CPU_type] if CPU_type in CPU_TYPES else "unknow"
        CPU_SubType = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
        file_type = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
        file_type = FILE_TYPES[file_type] if file_type in FILE_TYPES else "unknow"
        lc_num = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
        lc_size = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
        flags = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
        if self._arch == 64:
            self._f.read(4)

        # parser load commands
        self._parse_load_commands(lc_num)

        if "__DATA" not in self._segments or "__objc_classlist" not in self._segments["__DATA"] or len(self._symbols) <= 0:
            self._f.seek(self._macho_offset)
            return self

        # parse relocation tables
        self._parse_relocation_table()

        # handle __objc_classlist
        self._parse_class_from_section("__objc_classlist")
        # handle __objc_nlclslist
        self._parse_class_from_section("__objc_nlclslist")

        # handle __cstring
        self._parse_string_from_section("__cstring", self._read_string)
        # handle __swift5_reflstr
        self._parse_string_from_section("__swift5_reflstr", self._read_string)
        # handle __ustring
        self._parse_string_from_section("__ustring", self._read_ustring)

        self._f.seek(self._macho_offset)
        return self

    def get_result(self) -> (dict, set):
        return self._class_infos, self._strings


class libParser(baseParser):
    
    def __init__(self, binary_file: str, extract_path: str = None, logger=None):
        """
        :param binary_file: the binary file that wants to be parsed.
        :param extract_path: the path that want to extract the macho file.
        :param logger:
        """
        super().__init__(logger)
        self._binary_file = binary_file
        self._extract_path = extract_path
        self._symbols = []
        self._class_infos = {}
        self._strings = set()
        self._target_paths = []
        self._byteorder = "little"

        self._f = None


    @staticmethod
    def _update(sour: dict, dest: dict) -> None:
        """
        update the source to destination.
        :param sour:
        :param dest:
        :return:
        """
        for key in sour:
            if key not in dest:
                dest[key] = sour[key]
                continue
            old = sour[key]
            new = dest[key]
            dest[key] = list(set(old).union(set(new)))


    def _parse_arch_symbol_table(self, symbol_table_offset: int, symbol_table_size: int) -> None:
        """
        parse the symbol table of an arch file and update to symbols.
        :param symbol_table_offset: the offset of symbol table
        :param symbol_table_size: the size of symbol table
        :return:
        """
        for _ in range(int(symbol_table_size / 8)):
            symbol_offset = int.from_bytes(self._f.read(4), byteorder="little")
            _ = self._f.read(4)
            symbol = self._read_string(symbol_table_offset + symbol_table_size + 4 + symbol_offset)
            self._symbols.append(symbol)


    def _parse_arch(self, arch_offset: int, size: int = None, sub_extract_path: str = None) -> None:
        """
        parse the arch file and update the class informations and strings.
        if extract_path is not none, extract the macho file to specific path.
        :param arch_offset: the offset of arch.
        :param sub_extract_path: the path that want to extract the macho file.
        :param size: the size of arch.
        :return: None
        """
        # record now position and goto arch_offset.
        now_offset = self._f.tell()

        self._f.seek(arch_offset)
        self._f.read(8)  # signature
        # symtab header
        symtab_name = self._read_string_from_bytes(self._f.read(16))
        '''
        symtab_timestamp = self.f.read(12).decode("utf-8")
        symtab_user_id = self.f.read(6).decode("utf-8")
        symtab_group_id = self.f.read(6).decode("utf-8")
        symtab_mode_str = self.f.read(8).decode("utf-8")
        symtab_size_str = self.f.read(8).decode("utf-8")
        '''
        self._f.read(12 + 6 + 6 + 8 + 8)

        while self._f.read(2).hex() != "600a":
            pass
        symtab_long_name_len = int(symtab_name.strip()[3:])
        symtab_long_name = self._read_string_from_bytes(self._f.read(symtab_long_name_len))

        # symbol table
        symbol_table_size = int.from_bytes(self._f.read(4), byteorder="little")

        # symbols = parse_arch_symbol_table(f, self.f.tell(), symbol_table_size)
        self._f.seek(symbol_table_size, 1)

        # string table
        string_table_size = int.from_bytes(self._f.read(4), byteorder="little")
        self._f.seek(string_table_size, 1)

        # parse the all macho files
        while True:
            # object header
            object_name = self._read_string_from_bytes(self._f.read(16))
            '''
            object_timestamp = self.f.read(12).decode("utf-8")
            object_user_id = self.f.read(6).decode("utf-8")
            object_group_id = self.f.read(6).decode("utf-8")
            object_mode_str = self.f.read(8).decode("utf-8")
            '''
            self._f.read(12 + 6 + 6 + 8)

            object_size_str = self._read_string_from_bytes(self._f.read(8))
            while self._f.read(2).hex() != "600a":
                pass
            end_header_offset = self._f.tell()
            object_long_name_len = int(object_name.strip()[3:])
            object_long_name = self._read_string_from_bytes(self._f.read(object_long_name_len))
            print("handle " + object_long_name)

            if sub_extract_path is not None:
                target_path = os.path.join(sub_extract_path, object_long_name)
                with open(target_path, "wb") as f_:
                    f_.write(self._f.read(int(object_size_str) - object_long_name_len))
                self._target_paths.append(target_path)
            else:
                ret_class_infos, ret_strings = libParser_(self._f, self._binary_file, self._logger).parse_mach().get_result()
                self._update(ret_class_infos, self._class_infos)
                self._strings = ret_strings.union(self._strings)
            self._f.seek(end_header_offset + int(object_size_str))
            if self._f.tell() >= arch_offset + size:
                break

        self._f.seek(now_offset)


    def _parse_archs(self) -> None:
        """
        parse the all archs.
        :return:
        """
        arch_num = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
        for _ in range(arch_num):
            CPU_type = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
            CPU_type = CPU_TYPES[CPU_type] if CPU_type in CPU_TYPES else "unknow"
            CPU_SubType = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
            arch_offset = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
            arch_size = int.from_bytes(self._f.read(4), byteorder=self._byteorder)
            self._f.read(4)  # Align
            print("handle arch: ", CPU_type, CPU_SubType)

            sub_extract_path = None
            if self._extract_path is not None:
                sub_extract_path = os.path.join(self._extract_path, CPU_type + str(CPU_SubType))
                if not os.path.exists(sub_extract_path):
                    os.mkdir(sub_extract_path)
            self._parse_arch(arch_offset, arch_size, sub_extract_path)


    def parse(self):
        """
        parse the multi/single arch file and obj/macho file
        :return:
        """
        with open(self._binary_file, "rb") as f:
            self._f = f
            magic = self._f.read(8).hex()
            if magic == "213c617263683e0a":
                file_size = self._f.seek(0, 2) - self._f.seek(0)
                self._parse_arch(0, file_size, self._extract_path)
                return self
            self._f.seek(0)
            magic = self._f.read(4).hex()
            if magic == "cffaedfe" or magic == "cefaedfe":
                if self._extract_path is not None:
                    self._target_paths.append(self._binary_file)
                self._f.seek(0)
                self._class_infos, self._strings = libParser_(self._f, self._binary_file, self._logger).parse_mach().get_result()
                return self
            if magic == "cafebabe":
                self._byteorder = "big"
            elif magic == "bebafeca":
                self._byteorder = "little"
            else:
                return self
            self._parse_archs()
            return self


    def get_result(self):
        if not self._target_paths:
            return self._class_infos, self._strings
        else:
            return self._target_paths


def test_extract():
    parser = libParser("../jcore-ios-3.2.3.a", "./")
    for path in parser.parse().get_result():
        print(path)


def test_parse():
    # mach-o file path
    # path = r"D:\workplace\python\angr\viewer-sdk-ios-5b80ecde8420cad132c1863b3ccb1d5206acf1ae\AntourageWidget.xcframework\ios-arm64\AntourageWidget.framework\AntourageWidget"
    paths = [r"../../core/Payload/AOMMBank.app/AOMMBank",
             r"../../core/Payload/AppStore.app/AppStore",
             r"../../core/Payload/AssetTrust.app/AssetTrust",
             r"../../core/Payload/cgbapp.app/cgbapp",
             r"../../core/Payload/CGBMBank.app/CGBMBank",
             r"../libWeChatSDK.a",
             r"../jpush-ios-4.6.6.a",
             r"../jcore-ios-3.2.3.a",
             r"../../viewer-sdk-ios-5b80ecde8420cad132c1863b3ccb1d5206acf1ae\AntourageWidget.xcframework\ios-arm64\AntourageWidget.framework\AntourageWidget"]
    for path in paths:
        print("processing", path)
        parser = libParser(path)
        ret = parser.parse().get_result()
        print(ret[0], ret[1])


if __name__ == "__main__":
    test_extract()
    test_parse()
