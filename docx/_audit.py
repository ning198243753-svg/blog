from docx import Document
from docx.shared import Emu
import glob, os
for path in sorted(glob.glob(r"E:\project\blog\docx\0*.docx")):
    d = Document(path)
    sec = d.sections[0]
    usable = Emu(sec.page_width - sec.left_margin - sec.right_margin).cm
    over = []
    for i, t in enumerate(d.tables):
        w = sum((Emu(c.width).cm if c.width else 0) for c in t.rows[0].cells)
        if w > usable + 0.05:
            over.append((i, round(w, 2)))
    print(os.path.basename(path), "| tables=", len(d.tables),
          "| ours_overflow=", over, "| chars=", len(d.element.xml))
