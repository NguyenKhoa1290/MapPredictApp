"""Small bounded Protobuf and WebChannel framing helpers, no generated dependencies."""
import json

MAX_BYTES = 16 * 1024 * 1024


def varint(value):
    if type(value) is not int or value < 0 or value >= 2**64:
        raise ValueError('Invalid unsigned Protobuf integer')
    output = bytearray()
    while value >= 128:
        output.append((value & 127) | 128)
        value >>= 7
    output.append(value)
    return bytes(output)


def message(*entries):
    output = bytearray()
    for field, value in entries:
        if not 1 <= field < 2**29:
            raise ValueError('Invalid Protobuf field')
        if type(value) is int:
            output.extend(varint(field << 3) + varint(value))
        else:
            value = value.encode() if isinstance(value, str) else value
            if not isinstance(value, bytes):
                raise ValueError('Invalid Protobuf data')
            output.extend(varint((field << 3) | 2) + varint(len(value)) + value)
    if len(output) > MAX_BYTES:
        raise ValueError('Protobuf message too large')
    return bytes(output)


def fields(data):
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise ValueError('Invalid Protobuf message')
    index, count = 0, 0
    def read_varint():
        nonlocal index
        value = 0
        for shift in range(0, 70, 7):
            if index >= len(data):
                break
            byte = data[index]
            index += 1
            if shift == 63 and byte > 1:
                raise ValueError('Protobuf integer overflow')
            value |= (byte & 127) << shift
            if byte < 128:
                return value
        raise ValueError('Truncated Protobuf integer')
    while index < len(data):
        count += 1
        if count > 100000:
            raise ValueError('Too many Protobuf fields')
        tag = read_varint()
        field, wire = tag >> 3, tag & 7
        if not 1 <= field < 2**29:
            raise ValueError('Invalid Protobuf field')
        if wire == 0:
            value = read_varint()
        elif wire in (1, 2, 5):
            size = read_varint() if wire == 2 else 8 if wire == 1 else 4
            if index + size > len(data):
                raise ValueError('Truncated Protobuf field')
            value = data[index:index+size]
            index += size
        else:
            raise ValueError('Unsupported Protobuf wire type')
        yield field, wire, value


def get(data, field, default=None):
    return next((value for number, wire, value in fields(data) if number == field), default)


def at(data, *path):
    for field in path:
        if not isinstance(data, bytes):
            return None
        data = get(data, field)
        if data is None:
            return None
    return data


class Frames:
    def __init__(self):
        self.pending = b''

    def feed(self, chunk):
        self.pending += chunk
        if len(self.pending) > MAX_BYTES:
            raise ValueError('WebChannel frame too large')
        output = []
        while self.pending:
            newline = self.pending.find(b'\n')
            if newline < 0:
                if len(self.pending) > 12:
                    raise ValueError('Invalid WebChannel length')
                break
            prefix = self.pending[:newline]
            if not prefix.isdigit() or len(prefix) > 9:
                raise ValueError('Invalid WebChannel length')
            size = int(prefix)
            if size > MAX_BYTES:
                raise ValueError('WebChannel frame too large')
            end = newline + 1 + size
            if len(self.pending) < end:
                break
            output.append(json.loads(self.pending[newline+1:end]))
            self.pending = self.pending[end:]
        return output
