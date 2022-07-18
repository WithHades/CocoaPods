import json

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


def update(sour, dest):
    for key in sour:
        if key not in dest:
            dest[key] = sour[key]
            continue
        old = sour[key]
        new = dest[key]
        dest[key] = list(set(old).union(set(new)))


def readString(f, offset=None):
    now_offset = None
    if offset is not None:
        now_offset = f.tell()
        f.seek(offset)
    symbol = b"\x01"
    while symbol[-1] != 0:
        symbol += f.read(1)
    if offset is not None: f.seek(now_offset)
    return symbol[1:-1].decode("utf-8")


def decode(trans_bytes):
    index = trans_bytes.find(b"\x00")
    if index != -1:
        trans_bytes = trans_bytes[:index]
    return trans_bytes.decode("utf-8")


def trans_relo(f, relo_table, var_len, byteorder):
    if f.tell() in relo_table:
        ret = relo_table[f.tell()]
        f.read(var_len)
        return ret
    else:
        return int.from_bytes(f.read(var_len), byteorder=byteorder)


def parse_class(f, lib_offset, class_offset, relo_table, var_len, byteorder, segments, methType):
    class_infos = {}
    offet = f.tell()
    # parse class struct
    f.seek(lib_offset + class_offset)
    # print(methType, 1, hex(lib_offset + class_offset), hex(class_offset))
    isa_vm = trans_relo(f, relo_table, var_len, byteorder)
    if isa_vm != 0:
        class_offset = isa_vm - segments["__DATA"]["__objc_data"]["addr"] + segments["__DATA"]["__objc_data"]["offset"]
        class_info = parse_class(f, lib_offset, class_offset, relo_table, var_len, byteorder, segments, methType="+")
        update(class_info, class_infos)
    f.read(var_len * 3)  # skip superclass/cache/vtable
    # class data
    # const_offset_vm should be 0x2C9B
    const_offset_vm = trans_relo(f, relo_table, var_len, byteorder)
    const_offset = const_offset_vm - segments["__DATA"]["__objc_const"]["addr"] + segments["__DATA"]["__objc_const"]["offset"]
    # parse class info
    f.seek(lib_offset + const_offset)
    # for 32-bits, skip flags/instanceStart/instanceSize/ivarLayout
    # for 64-bits, skip flags/instanceStart/instanceSize/reserved/ivarLayout
    f.read(var_len * 4) if var_len == 4 else f.read(4 * 4 + var_len)

    class_name_offset_vm = trans_relo(f, relo_table, var_len, byteorder)
    base_methods_offset_vm = trans_relo(f, relo_table, var_len, byteorder)
    if base_methods_offset_vm == 0:
        # class doesn't have the method of methType
        f.seek(offet)
        return class_infos
    class_name_offset = class_name_offset_vm - segments["__TEXT"]["__objc_classname"]["addr"] + segments["__TEXT"]["__objc_classname"]["offset"]
    f.seek(lib_offset + class_name_offset)
    class_name = readString(f)
    class_info = {class_name: []}
    # parse base methods
    base_methods_offset = base_methods_offset_vm - segments["__DATA"]["__objc_const"]["addr"] + segments["__DATA"]["__objc_const"]["offset"]
    f.seek(lib_offset + base_methods_offset)
    entsize = int.from_bytes(f.read(4), byteorder=byteorder)
    count = int.from_bytes(f.read(4), byteorder=byteorder)
    for _ in range(count):
        method_name = trans_relo(f, relo_table, var_len, byteorder)
        method_types = trans_relo(f, relo_table, var_len, byteorder)
        method_imp = trans_relo(f, relo_table, var_len, byteorder)
        method_name = method_name - segments["__TEXT"]["__objc_methname"]["addr"] + segments["__TEXT"]["__objc_methname"]["offset"]
        method_name = readString(f, offset=lib_offset + method_name)
        class_info[class_name].append(methType + "[" + class_name + " " + method_name + "]")
    update(class_info, class_infos)
    f.seek(offet)
    return class_infos


def parse_segments(f, arch, byteorder):
    segments = {}
    var_len = 4 if arch == 32 else 8

    '''
    lc_segment_name = f.read(16).decode("utf-8")
    lc_vm_addr = int.from_bytes(f.read(var_len), byteorder=byteorder)
    lc_vm_size = int.from_bytes(f.read(var_len), byteorder=byteorder)
    lc_file_offset = int.from_bytes(f.read(var_len), byteorder=byteorder)
    lc_file_size = int.from_bytes(f.read(var_len), byteorder=byteorder)
    lc_max_pro = int.from_bytes(f.read(4), byteorder=byteorder)
    lc_init_pro = int.from_bytes(f.read(4), byteorder=byteorder)
    '''
    f.read(16 + var_len * 4 + 4 + 4)

    lc_sec_num = int.from_bytes(f.read(4), byteorder=byteorder)
    lc_flag = int.from_bytes(f.read(4), byteorder=byteorder)
    # parse section info
    for _ in range(lc_sec_num):
        section_name = decode(f.read(16))
        segment_name = decode(f.read(16))
        if segment_name not in segments: segments[segment_name] = {}
        segments[segment_name][section_name] = {}
        segments[segment_name][section_name]["addr"] = int.from_bytes(f.read(var_len), byteorder=byteorder)
        segments[segment_name][section_name]["size"] = int.from_bytes(f.read(var_len), byteorder=byteorder)
        segments[segment_name][section_name]["offset"] = int.from_bytes(f.read(4), byteorder=byteorder)
        segments[segment_name][section_name]["align"] = int.from_bytes(f.read(4), byteorder=byteorder)
        segments[segment_name][section_name]["relo_offset"] = int.from_bytes(f.read(4), byteorder=byteorder)
        segments[segment_name][section_name]["relo_num"] = int.from_bytes(f.read(4), byteorder=byteorder)
        segments[segment_name][section_name]["flags"] = int.from_bytes(f.read(4), byteorder=byteorder)

        # reserve
        f.read(8)
        if arch == 64: f.read(4)
    return segments


def parse_symtab(f, offset, var_len, byteorder):
    symbols = []
    symbol_table_offset = int.from_bytes(f.read(4), byteorder=byteorder)
    symbol_table_number = int.from_bytes(f.read(4), byteorder=byteorder)
    string_table_offset = int.from_bytes(f.read(4), byteorder=byteorder)
    string_table_size = int.from_bytes(f.read(4), byteorder=byteorder)
    _offset = f.tell()
    f.seek(offset + symbol_table_offset)
    for symbol in range(symbol_table_number):
        string_table_index = int.from_bytes(f.read(4), byteorder=byteorder)
        symbol_type = int.from_bytes(f.read(1), byteorder=byteorder)
        symbol_section_index = int.from_bytes(f.read(1), byteorder=byteorder)
        symbol_description = int.from_bytes(f.read(2), byteorder=byteorder)
        symbol_value = int.from_bytes(f.read(var_len), byteorder=byteorder)
        symbols.append([string_table_index, symbol_type, symbol_section_index, symbol_description, symbol_value])
    f.seek(_offset)
    return symbols


def parse_mach(f):
    offset = f.tell()
    # parse macho header
    magic = f.read(4)[::-1].hex()
    if magic == "feedface":
        arch = 32
    elif magic == "feedfacf":
        arch = 64
    else:
        return {}
    var_len = 4 if arch == 32 else 8
    byteorder = "little"
    CPU_type = int.from_bytes(f.read(4), byteorder=byteorder)
    CPU_type = CPU_TYPES[CPU_type] if CPU_type in CPU_TYPES else "unknow"
    CPU_SubType = int.from_bytes(f.read(4), byteorder=byteorder)
    file_type = int.from_bytes(f.read(4), byteorder=byteorder)
    file_type = FILE_TYPES[file_type] if file_type in FILE_TYPES else "unknow"
    lc_num = int.from_bytes(f.read(4), byteorder=byteorder)
    lc_size = int.from_bytes(f.read(4), byteorder=byteorder)
    flags = int.from_bytes(f.read(4), byteorder=byteorder)
    if arch == 64: f.read(4)

    # parse load commands
    segments = {}
    symbols = []
    for _ in range(lc_num):
        lc_cmd = int.from_bytes(f.read(4), byteorder=byteorder)
        lc_cmd_size = int.from_bytes(f.read(4), byteorder=byteorder)

        # parse segments info
        if lc_cmd == LCName.LC_SEGMENT_64 or lc_cmd == LCName.LC_SEGEMENT:
            segments = parse_segments(f, arch, byteorder)
        elif lc_cmd == LCName.LC_SYMTAB:
            symbols = parse_symtab(f, offset, var_len, byteorder)
        else:
            f.read(lc_cmd_size - 8)

    if "__DATA" not in segments or "__objc_classlist" not in segments["__DATA"]:
        f.seek(offset)
        return {}
    if len(symbols) <= 0:
        f.seek(offset)
        return {}

    relo_table = {}
    # handle relocation
    for segment in segments:
        for section in segments[segment]:
            section = segments[segment][section]
            section_offset = section["offset"]
            relo_offset = section["relo_offset"]
            relo_num = section["relo_num"]
            f.seek(offset + relo_offset)
            for relo in range(relo_num):
                addr = int.from_bytes(f.read(4), byteorder=byteorder)
                re_addr = section_offset + addr
                symbol_index = int.from_bytes(f.read(3), byteorder=byteorder)
                flag = int.from_bytes(f.read(1), byteorder=byteorder)
                r_type = (flag & 0xF0) >> 4
                r_extern = (flag & 0x8) >> 3
                r_pcrel = (flag & 0x4) >> 2
                r_length = flag & 0x3
                if r_extern == 1:
                    symbol_value = symbols[symbol_index][4]
                    relo_table[offset + re_addr] = symbol_value
    f.seek(offset + segments["__DATA"]["__objc_classlist"]["offset"])
    class_infos = {}
    for _ in range(int(segments["__DATA"]["__objc_classlist"]["size"] / var_len)):
        class_item_vm = trans_relo(f, relo_table, var_len, byteorder)
        class_offset = class_item_vm - segments["__DATA"]["__objc_data"]["addr"] + segments["__DATA"]["__objc_data"]["offset"]
        class_info = parse_class(f, offset, class_offset, relo_table, var_len, byteorder, segments, methType="-")
        update(class_info, class_infos)
    f.seek(offset)
    return class_infos


def parse_arch_symbol_table(f, symbol_table_offset, symbol_table_size):
    symbols = []
    for _ in range(int(symbol_table_size / 8)):
        symbol_offset = int.from_bytes(f.read(4), byteorder="little")
        _ = f.read(4)
        symbol = readString(f, symbol_table_offset + symbol_table_size + 4 + symbol_offset)
        symbols.append(symbol)
    return symbols


def parse_arch(f, offset, size=None):
    # record now position and goto offset.
    now_offset = f.tell()
    f.seek(offset)

    # start
    signature = f.read(8)

    # symtab header
    symtab_name = f.read(16).decode("utf-8")
    '''
    symtab_timestamp = f.read(12).decode("utf-8")
    symtab_user_id = f.read(6).decode("utf-8")
    symtab_group_id = f.read(6).decode("utf-8")
    symtab_mode_str = f.read(8).decode("utf-8")
    symtab_size_str = f.read(8).decode("utf-8")
    '''
    f.read(12 + 6 + 6 + 8 + 8)

    while f.read(2).hex() != "600a":
        pass
    symtab_long_name_len = int(symtab_name.strip()[3:])
    symtab_long_name = decode(f.read(symtab_long_name_len))

    # symbol table
    symbol_table_size = int.from_bytes(f.read(4), byteorder="little")

    # symbols = parse_arch_symbol_table(f, f.tell(), symbol_table_size)
    f.seek(symbol_table_size, 1)

    # string table
    string_table_size = int.from_bytes(f.read(4), byteorder="little")
    f.seek(string_table_size, 1)
    class_infos = {}
    while True:
        # object header
        object_name = f.read(16).decode("utf-8")
        '''
        object_timestamp = f.read(12).decode("utf-8")
        object_user_id = f.read(6).decode("utf-8")
        object_group_id = f.read(6).decode("utf-8")
        object_mode_str = f.read(8).decode("utf-8")
        '''
        f.read(12 + 6 + 6 + 8)

        object_size_str = f.read(8).decode("utf-8")
        while f.read(2).hex() != "600a":
            pass
        end_header_offset = f.tell()
        object_long_name_len = int(object_name.strip()[3:])
        object_long_name = decode(f.read(object_long_name_len))
        # print("handle " + object_long_name)
        ret = parse_mach(f)
        # print(object_long_name, " class infos: ", json.dumps(ret))
        class_infos.update(ret)
        f.seek(end_header_offset + int(object_size_str))
        if end_header_offset + int(object_size_str) >= offset + size:
            break

    f.seek(now_offset)
    return class_infos


def parse_archs(f, byteorder):
    class_infos = {}
    arch_num = int.from_bytes(f.read(4), byteorder=byteorder)
    for _ in range(arch_num):
        CPU_type = int.from_bytes(f.read(4), byteorder=byteorder)
        CPU_type = CPU_TYPES[CPU_type] if CPU_type in CPU_TYPES else "unknow"
        CPU_SubType = int.from_bytes(f.read(4), byteorder=byteorder)
        offset = int.from_bytes(f.read(4), byteorder=byteorder)
        size = int.from_bytes(f.read(4), byteorder=byteorder)
        f.read(4)  # Align
        # print("handle arch: ", CPU_type, CPU_SubType)
        class_info = parse_arch(f, offset, size)
        update(class_info, class_infos)
    return class_infos


def parse(path):
    with open(path, "rb") as f:
        magic = f.read(8).hex()
        if magic == "213c617263683e0a":
            file_size = f.seek(0, 2) - f.seek(0)
            class_infos = parse_arch(f, 0, file_size)
            return class_infos
        f.seek(0)
        magic = f.read(4).hex()
        if magic == "cffaedfe" or magic == "cefaedfe":
            f.seek(0)
            class_infos = parse_mach(f)
            return class_infos
        if magic == "cafebabe":
            byteorder = "big"
        elif magic == "bebafeca":
            byteorder = "little"
        else:
            return {}
        class_infos = parse_archs(f, byteorder)
        return class_infos


class_infos = parse("./jpushx86_64.a")
print(class_infos)
class_infos = parse("./jpush-ios-4.6.6.a")
print(class_infos)
class_infos = parse("./JPUSHService.o")
print(class_infos)
