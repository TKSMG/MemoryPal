import os
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path

os.environ.setdefault("MEMORYPAL_DATA_DIR", tempfile.mkdtemp(prefix="memorypal-tests-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal.core import extract_document_text  # noqa: E402
from memorypal.pdftext import PdfText  # noqa: E402


def build_pdf(objects, root=1):
    """Assemble numbered object bodies into a PDF with a valid xref table."""
    out = bytearray(b"%PDF-1.5\n")
    offsets = {}
    for number, body in objects.items():
        offsets[number] = len(out)
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    count = max(objects) + 1
    out += f"xref\n0 {count}\n0000000000 65535 f \n".encode()
    for number in range(1, count):
        out += f"{offsets.get(number, 0):010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {count} /Root {root} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def stream(data, compress=False):
    if compress:
        data = zlib.compress(data)
        return f"<< /Length {len(data)} /Filter /FlateDecode >>\nstream\n".encode() + data + b"\nendstream"
    return f"<< /Length {len(data)} >>\nstream\n".encode() + data + b"\nendstream"


def simple_pdf(compress=False):
    content = b"BT /F1 12 Tf 72 720 Td (Photosynthesis turns light into sugar.) Tj 0 -16 Td [(Chloro) -50 (phyll) -250 (is green.)] TJ ET"
    return build_pdf({
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R 6 0 R] /Count 2 >>",
        3: b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        5: stream(content, compress),
        6: b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /Contents 7 0 R >>",
        7: stream(b"BT /F1 12 Tf 72 720 Td (Page two \\(second\\) line) Tj ET", compress),
    })


def cid_pdf():
    """A Type0 font with a ToUnicode map, as Word and Google Docs export."""
    cmap = (b"/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
            b"1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
            b"2 beginbfchar <0003> <0020> <0010> <00E9> endbfchar\n"
            b"1 beginbfrange <0024> <003D> <0041> endbfrange\n"
            b"endcmap end end")
    # glyphs 0x24.. map to 'A'..; C=0x26 A=0x24 F=0x29 e-acute=0x10 space=0x03
    content = b"BT /F2 12 Tf 72 700 Td <00260024002900100003002500240027> Tj ET"
    return build_pdf({
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: b"<< /Type /Page /Parent 2 0 R /Resources 8 0 R /Contents 5 0 R >>",
        4: b"<< /Type /Font /Subtype /Type0 /BaseFont /Calibri /Encoding /Identity-H /ToUnicode 6 0 R >>",
        5: stream(content, compress=True),
        6: stream(cmap, compress=True),
        8: b"<< /Font << /F2 4 0 R >> >>",
    })


def object_stream_pdf():
    """Page and font objects stored inside a compressed object stream (PDF 1.5+)."""
    inner = [
        (3, b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"),
        (4, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
    ]
    header = b""
    body = b""
    for number, obj in inner:
        header += f"{number} {len(body)} ".encode()
        body += obj + b"\n"
    packed = zlib.compress(header + body)
    objstm = f"<< /Type /ObjStm /N {len(inner)} /First {len(header)} /Length {len(packed)} /Filter /FlateDecode >>\nstream\n".encode() + packed + b"\nendstream"
    return build_pdf({
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        5: stream(b"BT /F1 11 Tf 50 50 Td (Mitochondria make energy.) Tj ET", compress=True),
        9: objstm,
    })


def kerned_pdf():
    """Chrome/Edge style: each kerned piece placed with Tm/Td, widths in a nested /W."""
    cmap = (b"begincmap 7 beginbfchar <0001> <0057> <0010> <0061> <0011> <0074> <0012> <0065> "
            b"<0013> <0072> <0014> <0062> <0015> <0063> endbfchar endcmap")
    # "W" then "ater" nudged left by kerning; then a real gap before "cell".
    content = (b"BT /F1 16 Tf 1 0 0 -1 70 190 Tm <0001> Tj 13.5 0 Td <0010001100120013> Tj ET "
               b"BT /F1 16 Tf 1 0 0 -1 130 190 Tm <00140015> Tj ET")
    return build_pdf({
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        4: b"<< /Type /Font /Subtype /Type0 /Encoding /Identity-H /DescendantFonts [7 0 R] /ToUnicode 6 0 R >>",
        5: stream(content, compress=True),
        6: stream(cmap),
        7: b"<< /Type /Font /Subtype /CIDFontType2 /W [1 [944] 16 19 500] /DW 500 >>",
    })


class PdfTests(unittest.TestCase):
    def test_kerned_pieces_join_and_real_gaps_split(self):
        self.assertEqual(PdfText(kerned_pdf()).text(), "Water bc")

    def test_plain_and_compressed_pdfs(self):
        for compress in (False, True):
            text = PdfText(simple_pdf(compress)).text()
            self.assertIn("Photosynthesis turns light into sugar.", text)
            self.assertIn("Chlorophyll is green.", text)
            self.assertIn("Page two (second) line", text)
            self.assertLess(text.index("Photosynthesis"), text.index("Page two"))

    def test_cid_font_with_tounicode(self):
        self.assertIn("CAFé BAD", PdfText(cid_pdf()).text())

    def test_objects_inside_object_streams(self):
        self.assertIn("Mitochondria make energy.", PdfText(object_stream_pdf()).text())

    def test_pdf_file_through_document_import(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "notes.pdf"
            path.write_bytes(simple_pdf(True))
            self.assertIn("Photosynthesis", extract_document_text(path))

    def test_pdf_without_text_explains_itself(self):
        blank = build_pdf({
            1: b"<< /Type /Catalog /Pages 2 0 R >>",
            2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: b"<< /Type /Page /Parent 2 0 R /Contents 4 0 R >>",
            4: stream(b"q 100 0 0 100 0 0 cm /Im1 Do Q", True),
        })
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "scan.pdf"
            path.write_bytes(blank)
            with self.assertRaises(RuntimeError):
                extract_document_text(path)


class TextFileTests(unittest.TestCase):
    def write(self, name, data):
        path = Path(self.folder.name) / name
        path.write_bytes(data)
        return path

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.folder.cleanup()

    def test_encodings(self):
        sample = "Café notes: naïve résumé"
        cases = {
            "utf8.txt": sample.encode("utf-8"),
            "bom.txt": b"\xef\xbb\xbf" + sample.encode("utf-8"),
            "utf16.txt": sample.encode("utf-16"),  # Notepad "Unicode"
            "ansi.txt": sample.encode("cp1252"),
        }
        for name, data in cases.items():
            self.assertEqual(extract_document_text(self.write(name, data)).strip(), sample, name)

    def test_docx_keeps_line_breaks_and_tabs(self):
        xml = ('<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
               '<w:p><w:r><w:t>Term</w:t><w:tab/><w:t>Meaning</w:t></w:r></w:p>'
               '<w:p><w:r><w:t>Line one</w:t><w:br/><w:t>Line two</w:t></w:r></w:p>'
               '</w:body></w:document>')
        path = Path(self.folder.name) / "notes.docx"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("word/document.xml", xml)
        self.assertEqual(extract_document_text(path), "Term\tMeaning\nLine one\nLine two")

    def test_rtf(self):
        rtf = (r"{\rtf1\ansi{\fonttbl{\f0\fswiss Arial;}}{\colortbl;\red0\green0\blue0;}"
               r"\f0\fs24 Caf\'e9 \b bold\b0  words\par Second \{line\}\par " + chr(92) + "u8364? sign}")
        text = extract_document_text(self.write("notes.rtf", rtf.encode("ascii")))
        self.assertEqual(text, "Caf\u00e9 bold words\nSecond {line}\n\u20ac sign")


if __name__ == "__main__":
    unittest.main()
