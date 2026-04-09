"""
pdf_gen.py — PDF report generation using ReportLab.
3-page landscape A4 report with branded header & footer on every page.

  Page 1 · Title + Similar players (left) + Stats comparison (right)
  Page 2 · Radar (left) + Shooting % + Games & Minutes (right)
  Page 3 · Per-game volumes (full) + Ratios + Per-36 + Metrics legend
"""
import io, os, urllib.request
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker

import similarity as sim

# ── Asset paths ───────────────────────────────────────────────────
_ASSETS = os.path.join(os.path.dirname(__file__), "assets")
_LOGO_CACHE: dict = {}

def _el_logo_buf():
    """Return BytesIO of the EuroLeague logo PNG (downloaded once, cached)."""
    if "el" in _LOGO_CACHE:
        return _LOGO_CACHE["el"]

    # 1) Try local PNG converted by Dockerfile (rsvg-convert)
    png_path = os.path.join(_ASSETS, "euroleague_logo.png")
    if os.path.exists(png_path):
        with open(png_path, "rb") as f:
            data = f.read()
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            buf = io.BytesIO(data)
            _LOGO_CACHE["el"] = buf
            return buf

    # 2) Try Wikipedia thumbnail (works on HuggingFace)
    wiki_url = (
        "https://upload.wikimedia.org/wikipedia/en/thumb/"
        "2/2e/Euroleague_Basketball_logo.svg/"
        "200px-Euroleague_Basketball_logo.svg.png"
    )
    try:
        req = urllib.request.Request(wiki_url,
                                     headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=10).read()
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            buf = io.BytesIO(data)
            _LOGO_CACHE["el"] = buf
            return buf
    except Exception:
        pass

    # 3) Generate a simple orange "E" badge using matplotlib
    buf = _gen_el_badge()
    _LOGO_CACHE["el"] = buf
    return buf


def _ab_logo_buf():
    """Return BytesIO of the Analyzing Basketball logo (generated via matplotlib)."""
    if "ab" in _LOGO_CACHE:
        return _LOGO_CACHE["ab"]
    buf = _gen_ab_badge()
    _LOGO_CACHE["ab"] = buf
    return buf


def _gen_el_badge():
    """Minimal EuroLeague-style orange ball badge as PNG bytes."""
    from matplotlib.patches import Circle, Arc
    fig, ax = plt.subplots(figsize=(1.6, 1.6))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_aspect("equal"); ax.axis("off")
    fig.patch.set_alpha(0)
    ball = Circle((0.5, 0.5), 0.44, color="#f04e23", zorder=1)
    ax.add_patch(ball)
    # White curved stripes
    for off, w in [(0.14, 0.22), (-0.10, 0.18)]:
        arc = Arc((0.5, 0.5 + off), 0.78, 0.24,
                  angle=0, theta1=200, theta2=340,
                  color="white", lw=5, zorder=2)
        ax.add_patch(arc)
    ax.text(0.5, -0.08, "EuroLeague", ha="center", va="top",
            fontsize=6, fontweight="bold", color="#1a1a2e",
            fontfamily="sans-serif", transform=ax.transData)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=180, bbox_inches="tight",
                facecolor="none", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf


def _gen_ab_badge():
    """Analyzing Basketball brand badge as PNG bytes."""
    from matplotlib.patches import Circle
    fig, ax = plt.subplots(figsize=(2.2, 0.9))
    ax.set_xlim(0, 2.2); ax.set_ylim(0, 0.9)
    ax.set_aspect("equal"); ax.axis("off")
    fig.patch.set_alpha(0)
    # Basketball circle
    ball = Circle((0.45, 0.45), 0.38, color="#e07020", zorder=1)
    ax.add_patch(ball)
    for x in [(0.45, 0.07, 0.45, 0.83), (0.07, 0.45, 0.83, 0.45)]:
        ax.plot([x[0], x[2]], [x[1], x[3]], "k-", lw=0.8, zorder=2,
                transform=ax.transData)
    from matplotlib.patches import Arc
    for ang in [(0, 360, "k")]:
        pass
    # Text
    ax.text(0.92, 0.56, "Analyzing Basketball", ha="left", va="center",
            fontsize=7.5, fontweight="bold", color="#1a1a2e",
            fontfamily="sans-serif")
    ax.text(0.92, 0.26, "analyzingbasketball.com", ha="left", va="center",
            fontsize=5.5, color="#555555", fontfamily="sans-serif")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=180, bbox_inches="tight",
                facecolor="none", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf


# ── Font registration ─────────────────────────────────────────────

def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import matplotlib as mpl
    try:
        from matplotlib import font_manager as fm
        try:   reg  = fm.findfont("DejaVu Sans", fallback_to_default=False)
        except: reg  = mpl.get_data_path() + "/fonts/ttf/DejaVuSans.ttf"
        try:   bold = fm.findfont("DejaVu Sans:bold", fallback_to_default=False)
        except: bold = mpl.get_data_path() + "/fonts/ttf/DejaVuSans-Bold.ttf"
        pdfmetrics.registerFont(TTFont("DJS",  reg))
        pdfmetrics.registerFont(TTFont("DJSB", bold))
        return "DJS", "DJSB"
    except Exception:
        return "Helvetica", "Helvetica-Bold"


# ── Header / footer canvas decorator ─────────────────────────────

def _make_page_decorator(fr, fb):
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib import colors

    PW, PH = landscape(A4)
    M = 24          # page margin
    HDR_H = 38      # header band height
    FTR_H = 18      # footer band height

    def on_page(canvas, doc):
        canvas.saveState()

        # ── Header ──────────────────────────────────────────
        hdr_y = PH - M - HDR_H          # top of header band

        # AB logo (left)
        ab_buf = _ab_logo_buf()
        if ab_buf:
            ab_buf.seek(0)
            try:
                from reportlab.platypus import Image
                from reportlab.lib.utils import ImageReader
                ir = ImageReader(ab_buf)
                iw, ih = ir.getSize()
                scale = min(HDR_H * 3.0 / iw, HDR_H / ih)
                canvas.drawImage(ir, M, hdr_y,
                                 width=iw * scale, height=ih * scale,
                                 mask="auto")
            except Exception:
                canvas.setFont(fb, 9)
                canvas.setFillColor(colors.HexColor("#1a1a2e"))
                canvas.drawString(M, hdr_y + HDR_H / 2 - 4, "Analyzing Basketball")

        # EL logo (right)
        el_buf = _el_logo_buf()
        if el_buf:
            el_buf.seek(0)
            try:
                from reportlab.lib.utils import ImageReader
                ir = ImageReader(el_buf)
                iw, ih = ir.getSize()
                scale = min(HDR_H * 1.5 / iw, HDR_H / ih)
                logo_w = iw * scale
                canvas.drawImage(ir, PW - M - logo_w, hdr_y,
                                 width=logo_w, height=ih * scale,
                                 mask="auto")
            except Exception:
                canvas.setFont(fb, 8)
                canvas.setFillColor(colors.HexColor("#f04e23"))
                canvas.drawRightString(PW - M, hdr_y + HDR_H / 2 - 4, "EuroLeague")

        # Center text
        canvas.setFont(fb, 10)
        canvas.setFillColor(colors.HexColor("#1a1a2e"))
        canvas.drawCentredString(PW / 2, hdr_y + HDR_H * 0.60, "Analyzing Basketball")
        canvas.setFont(fr, 7.5)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawCentredString(PW / 2, hdr_y + HDR_H * 0.22,
                                 "EuroLeague Stats · 2025/26")

        # Blue rule below header
        canvas.setStrokeColor(colors.HexColor("#0047ff"))
        canvas.setLineWidth(1.2)
        canvas.line(M, hdr_y - 4, PW - M, hdr_y - 4)

        # ── Footer ──────────────────────────────────────────
        ftr_y = M                        # bottom of footer band

        # Light rule above footer
        canvas.setStrokeColor(colors.HexColor("#cccccc"))
        canvas.setLineWidth(0.5)
        canvas.line(M, ftr_y + FTR_H - 2, PW - M, ftr_y + FTR_H - 2)

        canvas.setFont(fr, 7)
        canvas.setFillColor(colors.HexColor("#888888"))

        # Left
        canvas.drawString(M, ftr_y + 4, "analyzingbasketball.com")
        # Centre
        canvas.drawCentredString(PW / 2, ftr_y + 4, f"Página {doc.page}")
        # Right
        canvas.drawRightString(PW - M, ftr_y + 4,
                               "EuroLeague Basketball · 2025/26")

        canvas.restoreState()

    return on_page


# ── Helpers ───────────────────────────────────────────────────────

def _f2(v):
    """Format any numeric to exactly 2 decimal places, or '—' if missing."""
    if v is None:
        return "—"
    try:
        fv = float(v)
        return "—" if np.isnan(fv) else f"{fv:.2f}"
    except (TypeError, ValueError):
        s = str(v).strip()
        return s if s else "—"


def _pct_vec(row, population):
    out = []
    for c in row.index:
        col_pop = population[c].dropna().values
        if len(col_pop) == 0 or pd.isna(row[c]):
            out.append(np.nan)
        else:
            out.append((np.sum(col_pop <= row[c]) / len(col_pop)) * 100.0)
    return pd.Series(out, index=row.index)


def _fig2img(fig, max_w, max_h, dpi=180):
    """Render matplotlib figure → ReportLab Image, scaled to fit (max_w × max_h) pts."""
    from reportlab.platypus import Image
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    w_in, h_in = fig.get_size_inches()
    plt.close(fig)
    buf.seek(0)
    w_pts, h_pts = w_in * 72, h_in * 72
    scale = min(max_w / w_pts, max_h / h_pts, 1.0)
    return Image(buf, width=w_pts * scale, height=h_pts * scale)


# ── Table builders ────────────────────────────────────────────────

def _base_style(fr, fb):
    from reportlab.lib import colors
    return [
        ("FONTNAME",       (0, 0), (-1,  0), fb),
        ("FONTNAME",       (0, 1), (-1, -1), fr),
        ("TEXTCOLOR",      (0, 0), (-1,  0), colors.white),
        ("BACKGROUND",     (0, 0), (-1,  0), colors.HexColor("#0047ff")),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",           (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f0f4ff")]),
        ("TOPPADDING",     (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
    ]


def _tbl_similar(rows, fr, fb):
    from reportlab.platypus import Table, TableStyle
    data = [["#", "Player", "Team", "Match %"]]
    for i, r in enumerate(rows, 1):
        data.append([str(i), r["player"], r.get("team", ""),
                     f"{r['correlation_pct']:.2f}%"])
    cw = [13, 90, 135, 46]
    cmds = _base_style(fr, fb) + [
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("ALIGN",    (0, 0), ( 0, -1), "CENTER"),
        ("ALIGN",    (3, 0), ( 3, -1), "RIGHT"),
    ]
    t = Table(data, colWidths=cw, repeatRows=1)
    t.setStyle(TableStyle(cmds))
    return t


def _tbl_stats(rows, p1, p2, fr, fb):
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors

    def _short(n, mx=18):
        return n if len(n) <= mx else n[: mx - 1] + "…"

    data = [["Metric", _short(p1), _short(p2)]]
    for r in rows:
        data.append([r["label"], _f2(r["p1"]), _f2(r["p2"])])

    cw = [68, 185, 185]
    cmds = _base_style(fr, fb) + [
        ("FONTSIZE",     (0, 0), (-1, -1), 6.5),
        ("TOPPADDING",   (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 2.5),
        ("ALIGN",        (1, 0), (-1, -1), "CENTER"),
    ]
    for i, r in enumerate(rows, 1):
        hib = r.get("higher_is_better")
        if hib is None:
            continue
        try:
            v1, v2 = float(r["p1"]), float(r["p2"])
        except (TypeError, ValueError):
            continue
        col = None
        if     hib and v1 > v2: col = 1
        elif   hib and v2 > v1: col = 2
        elif not hib and v1 < v2: col = 1
        elif not hib and v2 < v1: col = 2
        if col:
            cmds += [
                ("TEXTCOLOR", (col, i), (col, i), colors.HexColor("#0047ff")),
                ("FONTNAME",  (col, i), (col, i), fb),
            ]
    t = Table(data, colWidths=cw, repeatRows=1)
    t.setStyle(TableStyle(cmds))
    return t


def _tbl_legend(fr, fb):
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors

    entries = [
        ("G",        "Games played"),
        ("MIN/G",    "Minutes per game"),
        ("PTS",      "Points per game"),
        ("TRB",      "Total rebounds"),
        ("ORB",      "Offensive rebounds"),
        ("DRB",      "Defensive rebounds"),
        ("AST",      "Assists per game"),
        ("STL",      "Steals per game"),
        ("BLK",      "Blocks per game"),
        ("TOV",      "Turnovers"),
        ("FD",       "Fouls drawn"),
        ("FG%",      "Field goal %"),
        ("3P%",      "Three-point %"),
        ("2P%",      "Two-point %"),
        ("FT%",      "Free throw %"),
        ("eFG%",     "Effective FG%"),
        ("TS%",      "True shooting %"),
        ("3PAr",     "3PA ÷ FGA"),
        ("FTr",      "FTA ÷ FGA"),
        ("A/T",      "Assists ÷ Turnovers"),
        ("STL/TOV",  "Steals ÷ Turnovers"),
        ("PIR/G",    "Perf. Index Rating/G"),
        ("WIN%",     "Team win %"),
        ("START%",   "% games started"),
        ("_P36",     "Per 36 minutes"),
        ("Radar",    "Percentile 0–100 vs league"),
    ]
    half = (len(entries) + 1) // 2
    left, right = entries[:half], entries[half:]
    data = [["Abbr.", "Meaning", "Abbr.", "Meaning"]]
    for i in range(max(len(left), len(right))):
        l = left[i]  if i < len(left)  else ("", "")
        r = right[i] if i < len(right) else ("", "")
        data.append([l[0], l[1], r[0], r[1]])

    cw = [40, 84, 40, 84]
    cmds = _base_style(fr, fb) + [
        ("FONTSIZE",     (0, 0), (-1, -1), 6.5),
        ("TOPPADDING",   (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 2.5),
        ("FONTNAME",     (0, 1), ( 0, -1), fb),
        ("FONTNAME",     (2, 1), ( 2, -1), fb),
        ("TEXTCOLOR",    (0, 1), ( 0, -1), colors.HexColor("#0047ff")),
        ("TEXTCOLOR",    (2, 1), ( 2, -1), colors.HexColor("#0047ff")),
        ("LINEAFTER",    (1, 0), ( 1, -1), 0.8, colors.HexColor("#0047ff")),
    ]
    t = Table(data, colWidths=cw, repeatRows=1)
    t.setStyle(TableStyle(cmds))
    return t


# ── Main entry point ─────────────────────────────────────────────

def generate_pdf(p1, p2, k=5, include_same=False, team="", pos="", nat="",
                 age_min=0, age_max=99, corr_pct=None):
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    PageBreak, Table, TableStyle)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib import colors

    FR, FB = _register_fonts()
    dt = sim._df()
    for p in [p1, p2]:
        if p not in dt["Player"].values:
            raise ValueError(f"Player '{p}' not found.")

    # ── Source data ──────────────────────────────────────────────
    sim_result = sim.compute_similar(
        player=p1, team=team, pos=pos, nat=nat,
        age_min=age_min or 0, age_max=age_max or 99,
        k=k, include_same=include_same,
    )
    top_rows   = sim_result["similar"]
    stats_data = sim.get_player_stats(p1, p2)
    stats_rows = stats_data["rows"]
    per36_cols = sim._CACHE["per36_cols"]

    uniq  = dt.drop_duplicates("Player").set_index("Player")
    team1 = uniq.loc[p1, "Team"] if p1 in uniq.index else ""
    team2 = uniq.loc[p2, "Team"] if p2 in uniq.index else ""
    c1, c2 = sim._pair_colors(team1, team2)
    pair  = (dt[dt["Player"].isin([p1, p2])]
             .drop_duplicates("Player").set_index("Player").reindex([p1, p2]))
    pal = [c1, c2]

    # ── Doc setup (margins include header + footer space) ────────
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=24, rightMargin=24,
        topMargin=62,   # header band = ~38pt + 24pt gap
        bottomMargin=32,  # footer band = ~18pt + 14pt gap
    )
    W = doc.width    # ≈ 793 pt
    H = doc.height   # available height inside margins ≈ 503 pt

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("T1",  fontName=FB, fontSize=14,
                               alignment=TA_CENTER, spaceAfter=10))
    styles.add(ParagraphStyle("SH",  fontName=FB, fontSize=8.5,
                               textColor=colors.HexColor("#0047ff"),
                               alignment=TA_CENTER, spaceAfter=5))

    on_page = _make_page_decorator(FR, FB)
    elems = []
    corr_str = f" — {corr_pct:.1f}% match" if corr_pct is not None else ""

    # ══════════════════════════════════════════════════════════════
    # PAGE 1  ·  Title + Similar players (left) + Stats (right)
    # ══════════════════════════════════════════════════════════════
    elems.append(Paragraph(
        f"Head-to-Head: {p1} vs {p2}{corr_str}", styles["T1"]))

    sim_tbl  = _tbl_similar(top_rows, FR, FB)
    stat_tbl = _tbl_stats(stats_rows, p1, p2, FR, FB)
    gap = 16
    page1 = Table([[sim_tbl, Spacer(gap, 1), stat_tbl]],
                  colWidths=[W * 0.37, gap, W * 0.60])
    page1.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elems.append(page1)
    elems.append(PageBreak())

    # ══════════════════════════════════════════════════════════════
    # PAGE 2  ·  Radar (left) + Shooting % + G & Min (right)
    # ══════════════════════════════════════════════════════════════
    elems.append(Paragraph("Radar — Global percentiles (0–100)", styles["SH"]))

    radar_names = ["FG","FGA","3P","3PA","FT","FTA","TRB","STL","AST","TOV","BLK","PTS"]
    radar_cols  = [c for c in sim._present(dt, radar_names)
                   if c in pair.columns and c in dt.columns]
    radar_img = None
    if radar_cols and len(radar_cols) >= 3:
        pop = dt[radar_cols]
        rv1 = _pct_vec(pair.loc[p1, radar_cols], pop).values.tolist()
        rv2 = _pct_vec(pair.loc[p2, radar_cols], pop).values.tolist()
        lbls   = [c.upper() for c in radar_cols]
        rv1   += [rv1[0]]; rv2 += [rv2[0]]
        angles = np.linspace(0, 2*np.pi, len(lbls), endpoint=False).tolist() + [0]
        fig = plt.figure(figsize=(5.6, 5.8))
        ax  = fig.add_subplot(111, polar=True)
        ax.set_theta_offset(np.pi / 2); ax.set_theta_direction(-1)
        ax.set_facecolor("#f4f6fa")
        ax.set_xticks(angles[:-1], lbls); ax.tick_params(labelsize=7)
        ax.set_ylim(0, 100); ax.set_yticks([0, 20, 40, 60, 80, 100])
        l1, = ax.plot(angles, rv1, lw=2.3, color=c1, label=p1)
        ax.fill(angles, rv1, color=c1, alpha=0.25)
        l2, = ax.plot(angles, rv2, lw=2.3, color=c2, label=p2)
        ax.fill(angles, rv2, color=c2, alpha=0.25)
        ax.grid(color="gray", linestyle="dotted", alpha=0.5)
        fig.subplots_adjust(bottom=0.14)
        fig.legend(handles=[l1, l2], loc="lower center",
                   bbox_to_anchor=(0.5, 0.01), ncol=2, frameon=False, fontsize=8)
        radar_img = _fig2img(fig, W * 0.45, H * 0.88)

    # Shooting %
    pct_targets = ["FG%","3P%","2P%","EFG%","FT%","TS%"]
    pct_cols = [c for c in sim._present(dt, pct_targets) if c in pair.columns]
    pct_img  = None
    if pct_cols:
        fig, ax = plt.subplots(figsize=(5.3, 2.7))
        sub = pair[pct_cols].copy() * 100
        sub = sub.T; sub.index = [c.upper() for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, 108)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
        ax.set_title("Shooting %", pad=5, fontsize=8)
        ax.legend([p1, p2], fontsize=7, loc="upper right")
        plt.xticks(rotation=0, fontsize=7.5); plt.tight_layout()
        pct_img = _fig2img(fig, W * 0.52, H * 0.46)

    # Games & Minutes
    gm_cols = [c for c in sim._present(dt, ["G","MP"]) if c in pair.columns]
    gm_img  = None
    if gm_cols:
        fig, axes = plt.subplots(1, len(gm_cols), figsize=(5.3, 2.4))
        if len(gm_cols) == 1:
            axes = [axes]
        for i, c in enumerate(gm_cols):
            s = pair[[c]].T; s.index = [c.upper()]
            s.plot(kind="bar", ax=axes[i], color=pal, legend=False)
            axes[i].set_title(c.upper(), fontsize=8)
            axes[i].set_ylim(0, s.values.max() * 1.2 if s.size else 1)
            axes[i].tick_params(axis="x", labelbottom=False)
        axes[-1].legend([p1, p2], fontsize=7, loc="upper right")
        plt.suptitle("Games & Minutes", fontsize=8, y=1.02)
        plt.tight_layout()
        gm_img = _fig2img(fig, W * 0.52, H * 0.40)

    right_data = []
    if pct_img: right_data.append([pct_img])
    if pct_img and gm_img: right_data.append([Spacer(1, 8)])
    if gm_img:  right_data.append([gm_img])

    right_col = Spacer(1, 1)
    if right_data:
        right_col = Table(right_data)
        right_col.setStyle(TableStyle([
            ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))

    if radar_img:
        p2_tbl = Table([[radar_img, right_col]],
                       colWidths=[W * 0.46, W * 0.54])
        p2_tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
        ]))
        elems.append(p2_tbl)
    elif right_data:
        elems.append(right_col)
    elems.append(PageBreak())

    # ══════════════════════════════════════════════════════════════
    # PAGE 3  ·  Volumes (full) + Ratios + Per-36 + Legend
    # ══════════════════════════════════════════════════════════════
    elems.append(Paragraph("Per-game volumes", styles["SH"]))

    vol_targets = ["FG","FGA","3P","3PA","FT","FTA","TRB","AST","STL","BLK","TOV","PF","PTS"]
    vol_cols = [c for c in sim._present(dt, vol_targets) if c in pair.columns]
    if vol_cols:
        fig, ax = plt.subplots(figsize=(11.5, 3.0))
        sub = pair[vol_cols].T; sub.index = [c.upper() for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, sub.values.max() * 1.15 if sub.size else 1)
        ax.legend([p1, p2], fontsize=8, loc="upper right")
        plt.xticks(rotation=0, fontsize=8.5); plt.tight_layout()
        elems.append(_fig2img(fig, W * 0.98, H * 0.38))

    elems.append(Spacer(1, 8))
    elems.append(Paragraph("Advanced", styles["SH"]))

    # Advanced Ratios
    ratio_targets = ["3PAR","FTR","TOV%_SHOOT"]
    ratio_cols = [c for c in sim._present(dt, ratio_targets) if c in pair.columns]
    ratio_img  = None
    if ratio_cols:
        fig, ax = plt.subplots(figsize=(4.6, 2.8))
        sub = pair[ratio_cols].copy() * 100
        sub = sub.T; sub.index = [c.upper() for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, 108)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
        ax.set_title("Ratios", pad=5, fontsize=8)
        ax.legend([p1, p2], fontsize=7, loc="upper right")
        plt.xticks(rotation=0, fontsize=8); plt.tight_layout()
        ratio_img = _fig2img(fig, W * 0.30, H * 0.48)

    # Per 36 minutes
    p36c = [c for c in per36_cols if c in pair.columns]
    p36_img = None
    if p36c:
        fig, ax = plt.subplots(figsize=(5.4, 2.8))
        sub = pair[p36c].T
        sub.index = [c[:-7].upper() + "_P36" for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, sub.values.max() * 1.15 if sub.size else 1)
        ax.set_title("Per 36 minutes", pad=5, fontsize=8)
        ax.legend([p1, p2], fontsize=7, loc="upper right")
        plt.xticks(rotation=45, ha="right", fontsize=7.5); plt.tight_layout()
        p36_img = _fig2img(fig, W * 0.36, H * 0.48)

    leg = _tbl_legend(FR, FB)
    bottom = Table(
        [[ratio_img or Spacer(1, 1), p36_img or Spacer(1, 1), leg]],
        colWidths=[W * 0.30, W * 0.37, W * 0.33],
    )
    bottom.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
    ]))
    elems.append(bottom)

    doc.build(elems, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()
