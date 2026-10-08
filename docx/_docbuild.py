# -*- coding: utf-8 -*-
"""通用文档构建骨架：简约大气的现代版式。

被 02~07 各文档生成脚本复用，避免每个脚本重复 200 行版式代码。
"""
import re
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

CN_FONT = "微软雅黑"

# ---- 配色 ----
INK = RGBColor(0x14, 0x18, 0x1F)
NAVY = RGBColor(0x0F, 0x2E, 0x4C)
ACCENT = RGBColor(0x1E, 0x5C, 0xB8)
MUTED = RGBColor(0x6B, 0x76, 0x84)
GREEN = RGBColor(0x1B, 0x6B, 0x4A)
RED = RGBColor(0xA3, 0x36, 0x2B)
HAIR = "D8DEE6"
BOX_FILL = "F2F6FB"
HEAD_FILL = "EDF2F8"
ZEBRA_FILL = "F8FAFC"
HDR_BAR = "1E5CB8"
WARN_FILL = "FDF6EC"
WARN_BAR = "D98B2B"
OK_FILL = "F0F7F2"
OK_BAR = "2E7D5B"


def set_cn(run, font=CN_FONT):
    run.font.name = font
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    for attr in ("w:eastAsia", "w:ascii", "w:hAnsi"):
        rfonts.set(qn(attr), font)


def cell_shade(cell, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(shd)


def para_border(par, position="bottom", size=6, color=HAIR, space=6):
    ppr = par._p.get_or_add_pPr()
    borders = ppr.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        ppr.append(borders)
    bd = OxmlElement("w:" + position)
    bd.set(qn("w:val"), "single")
    bd.set(qn("w:sz"), str(size))
    bd.set(qn("w:space"), str(space))
    bd.set(qn("w:color"), color)
    borders.append(bd)


def cell_margins(table, top=60, bottom=60, left=110, right=110):
    mar = OxmlElement("w:tblCellMar")
    for tag, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        node = OxmlElement("w:" + tag)
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        mar.append(node)
    table._tbl.tblPr.append(mar)


def tbl_borders(table, edges):
    """edges: dict edge -> (sz, color)；sz=0 表示 none。sz 单位为 1/8 pt。"""
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        sz, color = edges.get(edge, (0, "auto"))
        el = OxmlElement("w:" + edge)
        if sz == 0:
            el.set(qn("w:val"), "none")
            el.set(qn("w:sz"), "0")
        else:
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), str(sz))
            el.set(qn("w:color"), color)
        el.set(qn("w:space"), "0")
        borders.append(el)
    table._tbl.tblPr.append(borders)


def hairline_table(table):
    tbl_borders(table, {
        "top": (8, "D8DEE6"), "bottom": (8, "D8DEE6"),
        "insideH": (4, "E6EBF1"),
    })


def left_bar_table(table, color=HDR_BAR, fill=None, size=18):
    tbl_borders(table, {"left": (size, color)})
    if fill:
        cell_shade(table.rows[0].cells[0], fill)


def keep_with_next(par):
    par._p.get_or_add_pPr().append(OxmlElement("w:keepNext"))


def keep_lines(par):
    par._p.get_or_add_pPr().append(OxmlElement("w:keepLines"))


def no_row_split(table):
    for row in table.rows:
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))


def repeat_header(table):
    node = OxmlElement("w:tblHeader")
    node.set(qn("w:val"), "true")
    table.rows[0]._tr.get_or_add_trPr().append(node)


def add_runs(par, text, size=None, color=None, base_bold=False):
    """解析 **加粗** 与 `等宽`；另支持 [[red]] / [[green]] 着色。"""
    pattern = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`|\[\[red\]\][\s\S]*?\[\[/\]\]|\[\[green\]\][\s\S]*?\[\[/\]\])")
    tokens = []
    idx = 0
    for m in pattern.finditer(text):
        if m.start() > idx:
            tokens.append(("plain", text[idx:m.start()]))
        raw = m.group(0)
        if raw.startswith("**"):
            tokens.append(("bold", raw[2:-2]))
        elif raw.startswith("`"):
            tokens.append(("code", raw[1:-1]))
        elif raw.startswith("[[red]]"):
            tokens.append(("red", raw[7:-4]))
        else:
            tokens.append(("green", raw[9:-4]))
        idx = m.end()
    if idx < len(text):
        tokens.append(("plain", text[idx:]))

    for kind, val in tokens:
        r = par.add_run(val)
        set_cn(r)
        if size:
            r.font.size = Pt(size)
        if color:
            r.font.color.rgb = color
        if base_bold or kind == "bold":
            r.bold = True
        if kind == "red":
            r.font.color.rgb = RED
            r.bold = True
        if kind == "green":
            r.font.color.rgb = GREEN
            r.bold = True
        if kind == "code":
            for attr in ("w:eastAsia", "w:ascii", "w:hAnsi"):
                r._element.rPr.rFonts.set(qn(attr), "Consolas")
            r.font.size = Pt((size or 10) - 0.5)
            r.font.color.rgb = RGBColor(0x0B, 0x4A, 0x6B)
    return par


class DocBuilder:
    def __init__(self, doc_path, title, subtitle, meta_lines):
        self.path = doc_path
        self.doc = Document()
        self._configure()
        self._cover(title, subtitle, meta_lines)

    # ---------- 基础版式 ----------
    def _configure(self):
        doc = self.doc
        for section in doc.sections:
            section.left_margin = section.right_margin = Cm(2.2)
            section.top_margin = section.bottom_margin = Cm(2.0)
            footer_par = section.footer.paragraphs[0]
            footer_par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run = footer_par.add_run()
            set_cn(run)
            run.font.size = Pt(8)
            run.font.color.rgb = MUTED
            b = OxmlElement("w:fldChar"); b.set(qn("w:fldCharType"), "begin")
            i = OxmlElement("w:instrText"); i.set(qn("xml:space"), "preserve"); i.text = "PAGE"
            e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), "end")
            run._r.append(b); run._r.append(i); run._r.append(e)

        st = doc.styles["Normal"]
        st.font.name = CN_FONT
        st.font.size = Pt(10)
        st.font.color.rgb = INK
        st.element.rPr.rFonts.set(qn("w:eastAsia"), CN_FONT)
        st.paragraph_format.space_after = Pt(7)
        st.paragraph_format.line_spacing = 1.45
        st.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE

        for name, (size, color, bold, before, after) in {
            "Title": (26, NAVY, True, 4, 28),
            "Heading 1": (16.5, NAVY, True, 20, 10),
            "Heading 2": (12.5, ACCENT, True, 14, 6),
            "Heading 3": (11, RGBColor(0x33, 0x3D, 0x4A), True, 10, 4),
        }.items():
            s = doc.styles[name]
            s.font.name = CN_FONT
            s.font.size = Pt(size)
            s.font.bold = bold
            s.font.color.rgb = color
            s.element.rPr.rFonts.set(qn("w:eastAsia"), CN_FONT)
            if name != "Title":
                ppr = s.element.get_or_add_pPr()
                for tag in ("w:pBdr", "w:shd"):
                    old = ppr.find(qn(tag))
                    if old is not None:
                        ppr.remove(old)
            s.paragraph_format.space_before = Pt(before)
            s.paragraph_format.space_after = Pt(after)

    def _cover(self, title, subtitle, meta_lines):
        tp = self.h("", 0)
        add_runs(tp, title)
        tp.paragraph_format.space_after = Pt(0)
        sub = self.p(subtitle, size=19, color=ACCENT)
        sub.paragraph_format.space_after = Pt(2)
        rule = self.doc.add_paragraph()
        rule.paragraph_format.space_before = Pt(2)
        rule.paragraph_format.space_after = Pt(2)
        para_border(rule, "bottom", size=12, color=HDR_BAR, space=1)
        for line in meta_lines:
            self.p(line, size=10, color=MUTED)
        self.doc.add_paragraph()

    # ---------- 内容元素 ----------
    def h(self, text, level=1):
        par = self.doc.add_heading("", level=level)
        add_runs(par, text)
        if level == 1:
            para_border(par, "bottom", size=8, color=HAIR, space=8)
        keep_with_next(par)
        return par

    def p(self, text, bold=False, size=None, color=None, italic=False):
        par = self.doc.add_paragraph()
        add_runs(par, text, size=size, color=color, base_bold=bold)
        if italic:
            for r in par.runs:
                r.italic = True
        keep_lines(par)
        return par

    def bullets(self, items, size=None):
        for it in items:
            par = self.doc.add_paragraph(style="List Bullet")
            par.paragraph_format.space_after = Pt(3)
            par.paragraph_format.left_indent = Cm(0.75)
            add_runs(par, it, size=size)

    def numbers(self, items, size=None):
        for it in items:
            par = self.doc.add_paragraph(style="List Number")
            par.paragraph_format.space_after = Pt(3)
            par.paragraph_format.left_indent = Cm(0.75)
            add_runs(par, it, size=size)

    def table(self, headers, rows, widths=None, font_size=9, first_col_bold=False):
        doc = self.doc
        t = doc.add_table(rows=1, cols=len(headers))
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        hairline_table(t)
        cell_margins(t)
        for i, name in enumerate(headers):
            cell = t.rows[0].cells[i]
            cell.text = ""
            par = cell.paragraphs[0]
            par.paragraph_format.space_after = Pt(0)
            par.paragraph_format.line_spacing = 1.2
            add_runs(par, name, size=font_size)
            for r in par.runs:
                r.bold = True
                r.font.color.rgb = NAVY
            cell_shade(cell, HEAD_FILL)
        for ri, row in enumerate(rows):
            cells = t.add_row().cells
            for i, val in enumerate(row):
                cells[i].text = ""
                par = cells[i].paragraphs[0]
                par.paragraph_format.space_after = Pt(0)
                par.paragraph_format.line_spacing = 1.25
                add_runs(par, str(val), size=font_size,
                         base_bold=(first_col_bold and i == 0))
                if ri % 2 == 1:
                    cell_shade(cells[i], ZEBRA_FILL)
        if widths:
            for row in t.rows:
                for i, w in enumerate(widths):
                    row.cells[i].width = Cm(w)
        no_row_split(t)
        repeat_header(t)
        self._gap()
        return t

    def snippet(self, lines, caption=None):
        """代码 / 配置片段块：等宽、浅底、无竖线。"""
        doc = self.doc
        t = doc.add_table(rows=1, cols=1)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        tbl_borders(t, {"top": (4, "DDE3EA"), "bottom": (4, "DDE3EA"),
                        "insideH": (4, "E6EBF1")})
        cell_margins(t, top=80, bottom=80, left=140, right=140)
        cell = t.rows[0].cells[0]
        cell.text = ""
        cell_shade(cell, "F7F9FB")
        cell.width = Cm(17.19)
        for i, line in enumerate(lines):
            par = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
            par.paragraph_format.space_after = Pt(0)
            par.paragraph_format.line_spacing = 1.15
            r = par.add_run(line)
            set_cn(r, "Consolas")
            for attr in ("w:eastAsia", "w:ascii", "w:hAnsi"):
                r._element.rPr.rFonts.set(qn(attr), "Consolas")
            r.font.size = Pt(8.5)
            r.font.color.rgb = RGBColor(0x1B, 0x2A, 0x38)
        if caption:
            cap = self.p(caption, size=8.5, color=MUTED)
            cap.paragraph_format.space_before = Pt(2)
        else:
            self._gap()
        return t

    def callout(self, title, body, kind="info"):
        fill, bar = {
            "info": (BOX_FILL, HDR_BAR),
            "warn": (WARN_FILL, WARN_BAR),
            "ok": (OK_FILL, OK_BAR),
        }[kind]
        t = self.doc.add_table(rows=1, cols=1)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        cell_margins(t, top=100, bottom=100, left=160, right=160)
        cell = t.rows[0].cells[0]
        cell.text = ""
        cell.width = Cm(17.19)
        cell_shade(cell, fill)
        par = cell.paragraphs[0]
        par.paragraph_format.space_after = Pt(0)
        par.paragraph_format.line_spacing = 1.4
        add_runs(par, "**%s** %s" % (title, body), size=9.5)
        left_bar_table(t, bar, fill=None)
        self._gap()
        return t

    def _gap(self):
        sp = self.doc.add_paragraph()
        sp.paragraph_format.space_before = Pt(0)
        sp.paragraph_format.space_after = Pt(0)
        sp.paragraph_format.line_spacing = Pt(4)
        r = sp.add_run("")
        set_cn(r)
        r.font.size = Pt(2)

    def chapter(self, num, title):
        self.doc.add_page_break()
        anchor = self.doc.add_paragraph()
        anchor.paragraph_format.space_before = Pt(0)
        anchor.paragraph_format.space_after = Pt(0)
        anchor.paragraph_format.line_spacing = Pt(10)
        r = anchor.add_run("")
        set_cn(r)
        r.font.size = Pt(1)
        self.h("%s. %s" % (num, title), 1)

    def save(self):
        self.doc.save(self.path)
        print("saved:", self.path)
