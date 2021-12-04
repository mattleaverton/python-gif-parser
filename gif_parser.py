import io
import math
from struct import unpack
from textwrap import wrap
from timeit import default_timer
from typing import List, Tuple


class Namespace(object):
    """ Pulled from ArgParse module """

    def __init__(self, **kwargs):
        for name in kwargs:
            setattr(self, name, kwargs[name])

    def __contains__(self, key):
        return key in self.__dict__


class _BinReader(object):
    _pointer = 0
    _cache = None

    def readable(self):
        return True

    def read(self):
        pass

    def read_bits(self, size):
        pass

    def read_bytes(self, size):
        data = self.read_bits(size * 8)
        data_as_byte_strings = wrap(data, 8)
        data_as_byte_list = [int(d, 2).to_bytes(1, byteorder="big") for d in data_as_byte_strings]
        return b"".join(data_as_byte_list)

    def read_bool(self):
        bit = self.read_bits(1)
        return bool(int(bit, 2))

    def read_string(self, length=1):
        data = self.read_bytes(length)
        data = data.decode("utf8")
        return data

    def read_bits_as_int(self, size, endianness="MSB"):
        return int(self.read_bits(size, endianness), 2)

    def read_uint8(self):
        byte = self.read_bytes(1)
        return ord(byte)

    def read_uint16(self, endianness="MSB"):
        byte_pair = bytearray(self.read_bytes(2))
        a = bin(byte_pair[0])[2:].zfill(8)
        b = bin(byte_pair[1])[2:].zfill(8)
        if endianness == "MSB":
            return int((a + b), 2)
        else:
            return int((b + a), 2)

    def read_packed_bits(self, args: List[Tuple[str, int]]) -> Namespace:
        ret_val = Namespace()
        for bit_name, num_bits in args:
            setattr(ret_val, bit_name, int(self.read_bits(num_bits), 2))
        return ret_val


class BinaryFileStream(io.FileIO, _BinReader):
    def read(self, size=-1):
        self._pointer = 0
        return super().read(size)

    def read_bits(self, size: int) -> str:
        pointer = self._pointer
        bits_left = 8 - self._pointer

        if size <= bits_left:
            # Get active byte from file, parse out bits and return as int
            data = super().read(1)
            data_as_bit_string = bin(ord(data))[2:].zfill(8)

            # Update pointer and reset file location
            self._pointer += size
            self._pointer %= 8
            if self._pointer != 0:
                super().seek(-1, 1)
            return data_as_bit_string[pointer:][:size]
        else:
            bytes_to_query = 1
            bytes_to_query += int(math.ceil((size - bits_left) / 8))
            data = bytearray(super().read(bytes_to_query))
            bit_data = [bin(data[0])[2:].zfill(8)[pointer:]]
            for d in data[1:]:
                bit_data.append(bin(d)[2:].zfill(8))
            data_as_bit_string = "".join(bit_data)[:size]

            self._pointer += size
            self._pointer %= 8
            if self._pointer != 0:
                super().seek(-1, 1)

            return data_as_bit_string

    def write(self, *args, **kwargs):
        raise io.UnsupportedOperation("Unsupported operation")


class BinaryStream(io.BytesIO, _BinReader):
    def read(self, size=-1):
        self._pointer = 0
        return super().read(size)

    def read_bits(self, size: int, endianness="MSB") -> str:
        pointer = self._pointer
        bits_left = 8 - self._pointer

        if size <= bits_left:
            # Get active byte from file, parse out bits and return as int
            data = super().read(1)
            data_as_bit_string = bin(ord(data))[2:].zfill(8)
            if endianness != "MSB":
                data_as_bit_string = data_as_bit_string[::-1]

            # Update pointer and reset file location
            self._pointer += size
            self._pointer %= 8
            if self._pointer != 0:
                super().seek(-1, 1)

            if endianness != "MSB":
                return data_as_bit_string[pointer:][:size][::-1]
            else:
                return data_as_bit_string[pointer:][:size]
        else:
            bytes_to_query = 1
            bytes_to_query += int(math.ceil((size - bits_left) / 8))
            data = bytearray(super().read(bytes_to_query))
            bit_data = []
            first_val = bin(data[0])[2:].zfill(8)
            if endianness != "MSB":
                bit_data.append(first_val[::-1][pointer:])
            else:
                bit_data.append(first_val[pointer:])
            for d in data[1:]:
                to_add = bin(d)[2:].zfill(8)
                if endianness != "MSB":
                    bit_data.append(to_add[::-1])
                else:
                    bit_data.append(to_add)
            data_as_bit_string = "".join(bit_data)[:size]

            self._pointer += size
            self._pointer %= 8
            if self._pointer != 0:
                super().seek(-1, 1)

            if endianness != "MSB":
                return data_as_bit_string[::-1]
            else:
                return data_as_bit_string


class GraphicControlExtension(Namespace):
    pass


class Frame(object):
    def __init__(self, img_pos, img_data, lzw_code: int = None,
                 color_table: list = None, graphic_extension: dict = None):
        self.left_position = img_pos[0]
        self.top_position = img_pos[1]
        self.width = img_pos[2]
        self.height = img_pos[3]
        self.color_table = color_table
        self.index_stream = []

        self.graphic_control_extension = graphic_extension
        if lzw_code is not None:
            # Frame to decode
            code_size = lzw_code + 1

            color_codes = pow(2, lzw_code)
            code_table = {}
            for i in range(color_codes):
                code_table[i] = [i]
            code_table[color_codes] = "clear"
            code_table[color_codes + 1] = "EOI"
            table_len = color_codes + 2

            with BinaryStream(img_data) as data:
                _clear = data.read_bits_as_int(code_size, endianness="LSB")
                init = data.read_bits_as_int(code_size, endianness="LSB")
                prev = init
                self.index_stream.extend(code_table[init])
                while True:
                    current = data.read_bits_as_int(code_size, endianness="LSB")
                    if current not in code_table:
                        k = code_table[prev][0]
                        if not isinstance(k, list):
                            k = [k]
                        code_table[current] = code_table[prev] + k
                        self.index_stream.extend(code_table[current])
                    else:
                        val = code_table[current]
                        if isinstance(val, str):
                            # Test for clear and EOI
                            if val == "EOI":
                                break
                            elif val == "clear":
                                code_size = lzw_code + 1
                                code_table = {}
                                for i in range(color_codes):
                                    code_table[i] = [i]
                                code_table[color_codes] = "clear"
                                code_table[color_codes + 1] = "EOI"
                                table_len = color_codes + 2
                                init = data.read_bits_as_int(code_size, endianness="LSB")
                                prev = init
                                self.index_stream.extend(code_table[init])
                                continue
                            else:
                                raise Exception("Unknown string decode command")
                        else:
                            self.index_stream.extend(val)
                            k = [val[0]]
                            try:
                                code_table[table_len] = code_table[prev] + k
                            except TypeError as e:
                                pass
                    if table_len >= pow(2, code_size) - 1:
                        code_size += 1
                        if code_size > 12:
                            code_size = 12
                    table_len += 1
                    prev = current
        else:
            # Frame to decode
            # Use the existing color_table if present, otherwise, create one
            pass

    def encode(self):
        pass

    def decode(self):
        pass


class GIF(object):
    def __init__(self, path):
        self.frames = []
        self.application_extension = None
        self.comments = []

        # with open(path, "rb") as f:
        with BinaryFileStream(path, "rb") as f:
            self.version = f.read_string(6)
            self.width = f.read_uint16("LSB")
            self.height = f.read_uint16("LSB")

            bitfield = f.read_packed_bits([
                ("global_color_table_flag", 1),
                ("color_resolution", 3),
                ("sort_flag", 1),
                ("size_of_global_color_table", 3)
            ])
            self.global_color_table = bool(bitfield.global_color_table_flag)
            self.bits_per_primary_color = bitfield.color_resolution + 1
            self.global_color_table_sorted = bool(bitfield.sort_flag)
            self.size_of_global_color_table = pow(2, bitfield.size_of_global_color_table + 1)

            self.bg_color_index = f.read_uint8()

            self.aspect_ratio = 0
            pixel_aspect_ratio = f.read_uint8()
            if pixel_aspect_ratio != 0:
                self.aspect_ratio = (pixel_aspect_ratio + 15) / 64

            self.global_colors = []
            if self.global_color_table:
                for color in range(self.size_of_global_color_table):
                    c = f.read_bytes(3)
                    self.global_colors.append({"r": c[0], "g": c[1], "b": c[2]})

            # 0x21 - ! marks comment block, plain text extension, application extension, graphic control extension,
            # 0x2C - , marks image
            # 0x3B - ; marks end
            temp_graphic_extension = None
            while True:
                sep = f.read(1)
                if sep == b";":
                    # End of file
                    break
                if sep == b"!":
                    # Comment block, plain text extension, application extension, or graphic control extension
                    extension = ord(f.read(1))
                    block_size = ord(f.read(1))
                    if extension == 0xFE:
                        # Comment Extension
                        comment = f.read(block_size)
                        _terminator = f.read(1)
                        self.comments.append(comment.decode("utf8"))
                    elif extension == 0xF9:
                        # Graphic Control Extension - specifies transparency and animation details
                        temp_graphic_extension = GraphicControlExtension()
                        bitfield = f.read_packed_bits([
                            ("reserved", 3),
                            ("disposal_method", 3),
                            ("user_input_flag", 1),
                            ("transparent_color_flag", 1),
                        ])
                        temp_graphic_extension.disposal_method = bitfield.disposal_method
                        temp_graphic_extension.user_input_flag = bitfield.user_input_flag
                        temp_graphic_extension.transparent_color_flag = bitfield.transparent_color_flag
                        temp_graphic_extension.delay_time = f.read_uint16("LSB") / 100.
                        temp_graphic_extension.transparent_color_index = f.read_uint8()
                        _terminator = f.read(1)
                    elif extension == 0x01:
                        # Plain Text Extension - mostly unused
                        text_extension = f.read(block_size)
                        _terminator = f.read(1)
                        print(f"Found plain text extension: {text_extension}")
                    elif extension == 0xFF:
                        # Application Extension
                        extension_type = f.read(block_size).decode("utf8")
                        extension_data_length = ord(f.read(1))
                        extension_code = unpack("B", f.read(1))[0]
                        assert extension_type.startswith("NETSCAPE") and extension_code == 1
                        extension_data = unpack("H", f.read(extension_data_length - 1))[0]
                        _terminator = f.read(1)
                        self.application_extension = {
                            "type": extension_type,
                            "loop_count": extension_data
                        }
                elif sep == b",":
                    # Image
                    img_left_position = f.read_uint16("LSB")
                    img_top_position = f.read_uint16("LSB")
                    img_width = f.read_uint16("LSB")
                    img_height = f.read_uint16("LSB")

                    bitfield = f.read_packed_bits([
                        ("local_color_table_flag", 1),
                        ("interlace_flag", 1),
                        ("sort_flag", 1),
                        ("reserved", 2),
                        ("size_of_local_color_table", 3),
                    ])
                    local_colors = []
                    if bool(bitfield.local_color_table_flag):
                        for color in range(bitfield.size_of_local_color_table):
                            c = f.read_bytes(3)
                            local_colors.append({"r": c[0], "g": c[1], "b": c[2]})

                    lzw_code = f.read_uint8()
                    img_data = bytearray()
                    while True:
                        img_block_size = ord(f.read(1))
                        if img_block_size == 0:
                            break
                        img_data.extend(f.read(img_block_size))

                    if bool(bitfield.local_color_table_flag):
                        color_table = list(local_colors)
                    else:
                        color_table = list(self.global_colors)

                    a = default_timer()
                    self.frames.append(Frame((img_left_position, img_top_position, img_width, img_height),
                                             img_data, lzw_code, color_table, temp_graphic_extension))
                    # print(f"frame processing took {default_timer() - a:.5f}s")
                    temp_graphic_extension = None
                else:
                    # Unexpected block
                    raise Exception(f"Unexpected block: {ord(sep)}")


if __name__ == "__main__":
    # file = r"images/test1.gif"
    # file = r"images/test2.gif"
    file = r"images/test3.gif"
    # file = r"images/test4.gif"
    t = default_timer()
    g = GIF(file)
    print(f"Frames: {len(g.frames)}")
    print(f"{g.width} x {g.height}")
    print(f"GIF decompress took {default_timer() - t:.4f}s")
