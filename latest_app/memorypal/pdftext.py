"""Pull the text out of ordinary PDFs with only the standard library.

Covers what note-taking apps, Word, Google Docs and most printers produce:
Flate-compressed content, object streams (PDF 1.5+), simple and Type0/CID
fonts with a ToUnicode map, and the common text operators. Scanned PDFs have
no text layer, so they return an empty string (that needs OCR).
"""

import re
import zlib

OBJECT_RE = re.compile(rb"(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj", re.S)
REF_RE = re.compile(rb"(\d+)\s+\d+\s+R")


class PdfText:
    def __init__(self, data):
        self.data = data
        self.objects = {}
        self.cmaps = {}
        self._collect_objects()

    # -- objects ---------------------------------------------------------
    def _collect_objects(self):
        for match in OBJECT_RE.finditer(self.data):
            self.objects[int(match.group(1))] = match.group(3)
        # Objects packed inside compressed object streams.
        for number, body in list(self.objects.items()):
            head = self.dict_part(body)
            if b"/ObjStm" not in head:
                continue
            stream = self.stream_data(body)
            if stream is None:
                continue
            first = self.int_value(head, b"/First")
            count = self.int_value(head, b"/N")
            if first is None or count is None:
                continue
            numbers = stream[:first].split()
            for index in range(min(count, len(numbers) // 2)):
                obj_number = int(numbers[index * 2])
                start = first + int(numbers[index * 2 + 1])
                end = first + int(numbers[index * 2 + 3]) if index + 1 < count and index * 2 + 3 < len(numbers) else len(stream)
                self.objects.setdefault(obj_number, stream[start:end])

    @staticmethod
    def dict_part(body):
        index = body.find(b"stream")
        return body if index < 0 else body[:index]

    @staticmethod
    def int_value(head, key):
        match = re.search(re.escape(key) + rb"\s+(\d+)", head)
        return int(match.group(1)) if match else None

    def stream_data(self, body):
        match = re.search(rb"stream\r?\n", body)
        if not match:
            return None
        head = body[:match.start()]
        raw = body[match.end():]
        end = raw.rfind(b"endstream")
        if end >= 0:
            raw = raw[:end]
        raw = raw.rstrip(b"\r\n")
        if b"/FlateDecode" in head or b"/Fl " in head or b"/Fl]" in head:
            try:
                return zlib.decompress(raw)
            except zlib.error:
                try:
                    return zlib.decompressobj().decompress(raw)
                except zlib.error:
                    return None
        if b"/Filter" in head:
            return None  # images and other encodings carry no text
        return raw

    def resolve(self, value):
        match = REF_RE.fullmatch(value.strip()) if value else None
        if match:
            return self.objects.get(int(match.group(1)), b"")
        return value

    def refs(self, value):
        return [int(number) for number in REF_RE.findall(value or b"")]

    def entry(self, body, key):
        """Raw value of `key` in a dictionary body: a ref, a <<dict>>, or an [array]."""
        match = re.search(re.escape(key) + rb"(?![A-Za-z])\s*", body)
        if not match:
            return None
        rest = body[match.end():]
        if rest.startswith(b"<<"):
            depth, index = 0, 0
            while index < len(rest) - 1:
                pair = rest[index:index + 2]
                if pair == b"<<":
                    depth += 1
                    index += 2
                    continue
                if pair == b">>":
                    depth -= 1
                    index += 2
                    if depth == 0:
                        return rest[:index]
                    continue
                index += 1
            return rest
        if rest.startswith(b"["):
            # Arrays can nest (a CIDFont's /W is full of inner [ ] lists).
            depth = 0
            for index, byte in enumerate(rest):
                if byte == 0x5B:
                    depth += 1
                elif byte == 0x5D:
                    depth -= 1
                    if depth == 0:
                        return rest[:index + 1]
            return rest
        ref = re.match(rb"\d+\s+\d+\s+R", rest)
        if ref:
            return ref.group(0)
        token = re.match(rb"[^\s/<>\[\]]+|/[^\s/<>\[\]]+", rest)
        return token.group(0) if token else None

    # -- pages -----------------------------------------------------------
    def pages(self):
        root_match = re.search(rb"/Root\s+(\d+)\s+\d+\s+R", self.data)
        ordered = []
        if root_match:
            catalog = self.objects.get(int(root_match.group(1)), b"")
            pages_ref = self.entry(catalog, b"/Pages")
            if pages_ref:
                self._walk_pages(pages_ref, ordered, set(), {})
        if not ordered:
            for number, body in self.objects.items():
                head = self.dict_part(body)
                if re.search(rb"/Type\s*/Page(?![s\w])", head):
                    ordered.append((number, None))
        return ordered

    def _walk_pages(self, ref, ordered, seen, inherited):
        for number in self.refs(ref):
            if number in seen:
                continue
            seen.add(number)
            body = self.dict_part(self.objects.get(number, b""))
            resources = self.entry(body, b"/Resources") or inherited.get("resources")
            if re.search(rb"/Type\s*/Pages", body):
                kids = self.entry(body, b"/Kids")
                self._walk_pages(kids or b"", ordered, seen, {"resources": resources})
            else:
                ordered.append((number, resources))

    def page_fonts(self, page_body, resources):
        resources = self.resolve(resources) if resources else None
        if resources is None:
            resources = self.resolve(self.entry(page_body, b"/Resources") or b"")
        fonts = self.resolve(self.entry(resources or b"", b"/Font") or b"")
        mapping = {}
        for name, number in re.findall(rb"/([^\s/<>\[\]]+)\s+(\d+)\s+\d+\s+R", fonts or b""):
            mapping[name] = self.font_cmap(int(number))
        return mapping

    # -- fonts -----------------------------------------------------------
    def font_cmap(self, number):
        """(ToUnicode map, two-byte codes?, glyph widths, default width) for a font."""
        if number in self.cmaps:
            return self.cmaps[number]
        body = self.objects.get(number, b"")
        head = self.dict_part(body)
        cmap = None
        ref = self.entry(head, b"/ToUnicode")
        if ref:
            stream = self.stream_data(self.resolve(ref))
            if stream:
                cmap = parse_cmap(stream)
        two_byte = b"/Type0" in head or b"Identity-H" in head
        widths, default = {}, 500.0
        if two_byte:
            descendants = self.entry(head, b"/DescendantFonts") or b""
            descendants = self.resolve(descendants) if REF_RE.fullmatch(descendants.strip() or b"-") else descendants
            for cid_ref in self.refs(descendants)[:1]:
                cid_font = self.dict_part(self.objects.get(cid_ref, b""))
                dw = re.search(rb"/DW\s+([\d.]+)", cid_font)
                default = float(dw.group(1)) if dw else 1000.0
                widths = parse_cid_widths(self.resolve(self.entry(cid_font, b"/W") or b""))
        else:
            first = self.int_value(head, b"/FirstChar") or 0
            array = self.resolve(self.entry(head, b"/Widths") or b"")
            for offset, value in enumerate(re.findall(rb"[-+]?\d*\.?\d+", array or b"")):
                widths[first + offset] = float(value)
        self.cmaps[number] = (cmap, two_byte, widths, default)
        return self.cmaps[number]

    # -- text ------------------------------------------------------------
    def text(self):
        pages = []
        for number, resources in self.pages():
            body = self.objects.get(number, b"")
            head = self.dict_part(body)
            fonts = self.page_fonts(head, resources)
            contents = self.entry(head, b"/Contents") or b""
            streams = []
            for ref in self.refs(contents):
                data = self.stream_data(self.objects.get(ref, b""))
                if data is None:
                    # A /Contents ref can point to an array of more refs.
                    inner = self.objects.get(ref, b"")
                    for inner_ref in self.refs(inner):
                        data_inner = self.stream_data(self.objects.get(inner_ref, b""))
                        if data_inner:
                            streams.append(data_inner)
                    continue
                streams.append(data)
            text = run_content(b"\n".join(streams), fonts)
            if text.strip():
                pages.append(text.strip())
        return "\n\n".join(pages)


def parse_cmap(data):
    mapping = {}

    def hex_text(value):
        raw = bytes.fromhex(value.decode("ascii"))
        try:
            return raw.decode("utf-16-be")
        except UnicodeDecodeError:
            return raw.decode("latin-1")

    for block in re.findall(rb"beginbfchar(.*?)endbfchar", data, re.S):
        for source, target in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", block):
            mapping[int(source, 16)] = hex_text(target)
    for block in re.findall(rb"beginbfrange(.*?)endbfrange", data, re.S):
        for start, end, target in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]*>|\[[^\]]*\])", block):
            low, high = int(start, 16), int(end, 16)
            if target.startswith(b"["):
                for offset, item in enumerate(re.findall(rb"<([0-9A-Fa-f]*)>", target)):
                    mapping[low + offset] = hex_text(item)
            else:
                base = bytes.fromhex(target[1:-1].decode("ascii"))
                if not base:
                    continue
                prefix, last = base[:-2] if len(base) >= 2 else b"", int.from_bytes(base[-2:], "big")
                for offset in range(0, min(high - low, 65535) + 1):
                    value = prefix + (last + offset).to_bytes(2, "big")
                    try:
                        mapping[low + offset] = value.decode("utf-16-be")
                    except UnicodeDecodeError:
                        continue
    return mapping


TOKEN_RE = re.compile(rb"\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>|\[|\]|/[^\s/\[\]()<>]+|[-+]?\d*\.?\d+|[A-Za-z'\"*]+")


def literal_bytes(token):
    """Decode a (literal string) token, handling escapes and nested parens."""
    body = token[1:-1]
    out = bytearray()
    index = 0
    escapes = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f"}
    while index < len(body):
        char = body[index:index + 1]
        if char == b"\\" and index + 1 < len(body):
            nxt = body[index + 1:index + 2]
            if nxt in escapes:
                out += escapes[nxt]
                index += 2
            elif nxt.isdigit():
                digits = re.match(rb"[0-7]{1,3}", body[index + 1:]).group(0)
                out.append(int(digits, 8) & 0xFF)
                index += 1 + len(digits)
            elif nxt in (b"\n", b"\r"):
                index += 2
            else:
                out += nxt
                index += 2
        else:
            out += char
            index += 1
    return bytes(out)


def parse_cid_widths(array):
    """CIDFont /W: `c [w1 w2 ...]` and `first last w` entries."""
    widths = {}
    tokens = re.findall(rb"\[|\]|[-+]?\d*\.?\d+", array or b"")
    if tokens and tokens[0] == b"[":
        tokens = tokens[1:-1] if tokens[-1] == b"]" else tokens[1:]
    index = 0
    while index < len(tokens):
        try:
            start = int(float(tokens[index]))
        except ValueError:
            index += 1
            continue
        if index + 1 < len(tokens) and tokens[index + 1] == b"[":
            index += 2
            code = start
            while index < len(tokens) and tokens[index] != b"]":
                widths[code] = float(tokens[index])
                code += 1
                index += 1
            index += 1
        elif index + 2 < len(tokens):
            end, width = int(float(tokens[index + 1])), float(tokens[index + 2])
            for code in range(start, min(end, start + 65535) + 1):
                widths[code] = width
            index += 3
        else:
            break
    return widths


def string_codes(raw, font):
    two_byte = bool(font and (font[1] or (font[0] and max(font[0], default=0) > 255)))
    width = 2 if two_byte else 1
    return [int.from_bytes(raw[index:index + width], "big") for index in range(0, len(raw) - width + 1, width)]


def decode_string(raw, font):
    cmap = font[0] if font else None
    two_byte = font[1] if font else False
    if cmap:
        return "".join(cmap.get(code, "") for code in string_codes(raw, font))
    if two_byte:
        try:
            return raw.decode("utf-16-be")
        except UnicodeDecodeError:
            return ""
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", "ignore")
    return raw.decode("cp1252", "replace")


def string_advance(raw, font):
    """Width of a string in thousandths of the font size."""
    widths = font[2] if font else {}
    default = font[3] if font else 500.0
    if not widths:
        default = default if font and font[1] else 500.0
    return sum(widths.get(code, default) for code in string_codes(raw, font))


def run_content(data, fonts):
    """Interpret the text operators of a content stream into lines of text.

    Positions are tracked with the fonts' real glyph widths, so a new text
    position right where the previous text ended (kerning, as Chrome/Edge
    and many exporters write it) joins the word, while a visible gap becomes
    a space and a move to another line starts a new line.
    """
    tokens = TOKEN_RE.findall(data)
    operands = []
    array_items = None
    font = None
    size = 12.0
    scale = 1.0
    lines = []
    line = []
    state = {"x": 0.0, "line_x": 0.0, "y": None}

    def newline():
        if line:
            lines.append("".join(line).strip())
            line.clear()

    def move_to(x, y):
        """Start drawing at (x, y) in text-matrix units."""
        gap_limit = max(0.5, abs(size * scale) * 0.18)
        if state["y"] is not None and abs(y - state["y"]) > max(0.5, abs(size * scale) * 0.4):
            newline()
        elif line and (x - state["x"] > gap_limit or x < state["line_x"] - gap_limit) and not line[-1].endswith(" "):
            line.append(" ")
        state["x"] = x
        state["y"] = y

    def show(raw):
        line.append(decode_string(raw, font))
        state["x"] += string_advance(raw, font) / 1000.0 * size * scale

    for token in tokens:
        if token == b"[":
            array_items = []
            continue
        if token == b"]":
            operands.append(("array", array_items or []))
            array_items = None
            continue
        if token.startswith(b"(") or token.startswith(b"<"):
            if token.startswith(b"("):
                raw = literal_bytes(token)
            else:
                digits = re.sub(rb"\s", b"", token[1:-1])
                raw = bytes.fromhex((digits + (b"0" if len(digits) % 2 else b"")).decode("ascii"))
            (array_items if array_items is not None else operands).append(("str", raw))
            continue
        if re.fullmatch(rb"[-+]?\d*\.?\d+", token):
            (array_items if array_items is not None else operands).append(("num", float(token)))
            continue
        if token.startswith(b"/"):
            operands.append(("name", token[1:]))
            continue
        op = token
        numbers = [value for kind, value in operands if kind == "num"]
        if op == b"Tf":
            names = [value for kind, value in operands if kind == "name"]
            if names:
                font = fonts.get(names[-1])
            if numbers:
                size = numbers[-1] or size
        elif op == b"BT":
            state.update(x=0.0, line_x=0.0)
            scale = 1.0
        elif op == b"Tm" and len(numbers) >= 6:
            a, b_, _c, _d, e, f = numbers[-6:]
            scale = (a * a + b_ * b_) ** 0.5 or 1.0
            move_to(e, f)
            state["line_x"] = e
        elif op in (b"Td", b"TD") and len(numbers) >= 2:
            tx, ty = numbers[-2] * scale, numbers[-1] * scale
            x = state["line_x"] + tx
            move_to(x, (state["y"] or 0.0) + ty)
            state["line_x"] = x
        elif op in (b"T*", b"'", b'"'):
            newline()
            state["x"] = state["line_x"]
            if op != b"T*":
                strings = [value for kind, value in operands if kind == "str"]
                if strings:
                    show(strings[-1])
        elif op == b"Tj":
            strings = [value for kind, value in operands if kind == "str"]
            if strings:
                show(strings[-1])
        elif op == b"TJ":
            arrays = [value for kind, value in operands if kind == "array"]
            if arrays:
                for kind, value in arrays[-1]:
                    if kind == "str":
                        show(value)
                    else:
                        shift = -value / 1000.0 * size * scale
                        state["x"] += shift
                        if value < -180 and line and not line[-1].endswith(" "):
                            line.append(" ")  # a wide gap inside TJ is a word space
        elif op == b"ET":
            pass
        operands = []
    newline()
    text = "\n".join(value for value in lines if value)
    return re.sub(r"[ \t]{2,}", " ", text)


def extract_pdf_text(path):
    with open(path, "rb") as handle:
        data = handle.read()
    return PdfText(data).text()
