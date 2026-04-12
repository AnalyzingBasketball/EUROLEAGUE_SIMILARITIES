"""
pdf_gen.py — PDF report generation using ReportLab.
Generates a multi-page head-to-head comparison report.
Header/footer with logos on every page.
"""
import io, os, unicodedata, urllib.request
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import similarity as sim

_ASSETS = os.path.join(os.path.dirname(__file__), "assets")
_LOGO_CACHE: dict = {}


# ── Logo helpers ──────────────────────────────────────────────────

def _el_logo_buf():
    if "el" in _LOGO_CACHE:
        return _LOGO_CACHE["el"]
    png_path = os.path.join(_ASSETS, "euroleague_logo.png")
    if os.path.exists(png_path):
        with open(png_path, "rb") as f:
            data = f.read()
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            buf = io.BytesIO(data)
            _LOGO_CACHE["el"] = buf
            return buf
    try:
        url = ("https://upload.wikimedia.org/wikipedia/en/thumb/"
               "2/2e/Euroleague_Basketball_logo.svg/"
               "200px-Euroleague_Basketball_logo.svg.png")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=8).read()
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            buf = io.BytesIO(data)
            _LOGO_CACHE["el"] = buf
            return buf
    except Exception:
        pass
    buf = _gen_el_badge()
    _LOGO_CACHE["el"] = buf
    return buf


def _gen_el_badge():
    from matplotlib.patches import Circle, Arc
    fig, ax = plt.subplots(figsize=(1.4, 1.4))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_aspect("equal"); ax.axis("off")
    fig.patch.set_alpha(0)
    ax.add_patch(Circle((0.5, 0.5), 0.44, color="#f04e23", zorder=1))
    for off in [0.14, -0.10]:
        ax.add_patch(Arc((0.5, 0.5 + off), 0.78, 0.24,
                         angle=0, theta1=200, theta2=340,
                         color="white", lw=5, zorder=2))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=180, bbox_inches="tight",
                facecolor="none", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf


def _gen_ab_badge():
    from matplotlib.patches import Circle
    fig, ax = plt.subplots(figsize=(2.0, 0.8))
    ax.set_xlim(0, 2.0); ax.set_ylim(0, 0.8)
    ax.set_aspect("equal"); ax.axis("off")
    fig.patch.set_alpha(0)
    ax.add_patch(Circle((0.4, 0.4), 0.34, color="#e07020", zorder=1))
    ax.plot([0.4, 0.4], [0.06, 0.74], "k-", lw=0.8, zorder=2)
    ax.plot([0.06, 0.74], [0.4, 0.4], "k-", lw=0.8, zorder=2)
    ax.text(0.85, 0.52, "Analyzing Basketball", ha="left", va="center",
            fontsize=7, fontweight="bold", color="#1a1a2e", fontfamily="sans-serif")
    ax.text(0.85, 0.24, "analyzingbasketball.com", ha="left", va="center",
            fontsize=5, color="#555555", fontfamily="sans-serif")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=180, bbox_inches="tight",
                facecolor="none", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf


# ── Header / footer decorator ─────────────────────────────────────

def _make_page_decorator(fr, fb):
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader

    PW, PH = landscape(A4)
    LM, HDR_H, FTR_H = 24, 34, 16

    def on_page(canvas, doc):
        canvas.saveState()
        hdr_y = PH - LM - HDR_H

        # AB logo (left)
        try:
            ab = _gen_ab_badge(); ab.seek(0)
            ir = ImageReader(ab); iw, ih = ir.getSize()
            scale = min(HDR_H * 2.8 / iw, HDR_H / ih)
            canvas.drawImage(ir, LM, hdr_y, width=iw * scale, height=ih * scale, mask="auto")
        except Exception:
            canvas.setFont(fb, 8)
            canvas.setFillColor(colors.HexColor("#1a1a2e"))
            canvas.drawString(LM, hdr_y + HDR_H * 0.3, "Analyzing Basketball")

        # EL logo (right)
        try:
            el = _el_logo_buf(); el.seek(0)
            ir = ImageReader(el); iw, ih = ir.getSize()
            scale = min(HDR_H * 1.4 / iw, HDR_H / ih)
            lw = iw * scale
            canvas.drawImage(ir, PW - LM - lw, hdr_y, width=lw, height=ih * scale, mask="auto")
        except Exception:
            canvas.setFont(fb, 8)
            canvas.setFillColor(colors.HexColor("#f04e23"))
            canvas.drawRightString(PW - LM, hdr_y + HDR_H * 0.3, "EuroLeague")

        # Centre text
        canvas.setFont(fb, 9)
        canvas.setFillColor(colors.HexColor("#1a1a2e"))
        canvas.drawCentredString(PW / 2, hdr_y + HDR_H * 0.58, "Analyzing Basketball")
        canvas.setFont(fr, 7)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawCentredString(PW / 2, hdr_y + HDR_H * 0.18, "EuroLeague Stats · 2025/26")

        # Blue rule below header
        canvas.setStrokeColor(colors.HexColor("#0047ff"))
        canvas.setLineWidth(1.0)
        canvas.line(LM, hdr_y - 3, PW - LM, hdr_y - 3)

        # Footer
        ftr_y = LM
        canvas.setStrokeColor(colors.HexColor("#cccccc"))
        canvas.setLineWidth(0.5)
        canvas.line(LM, ftr_y + FTR_H - 2, PW - LM, ftr_y + FTR_H - 2)
        canvas.setFont(fr, 6.5)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawString(LM, ftr_y + 3, "analyzingbasketball.com")
        canvas.drawCentredString(PW / 2, ftr_y + 3, f"Página {doc.page}")
        canvas.drawRightString(PW - LM, ftr_y + 3, "EuroLeague Basketball · 2025/26")

        canvas.restoreState()

    return on_page


# ── Helpers ───────────────────────────────────────────────────────

def _sanitize(text):
    norm = unicodedata.normalize("NFKD", str(text))
    return "".join(c if c.isalnum() else "_" for c in norm.encode("ascii", "ignore").decode()).strip("_")


def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import matplotlib as mpl
    try:
        from matplotlib import font_manager as fm
        try:   reg  = fm.findfont("DejaVu Sans", fallback_to_default=False)
        except: reg = mpl.get_data_path() + "/fonts/ttf/DejaVuSans.ttf"
        try:   bold = fm.findfont("DejaVu Sans:bold", fallback_to_default=False)
        except: bold = mpl.get_data_path() + "/fonts/ttf/DejaVuSans-Bold.ttf"
        pdfmetrics.registerFont(TTFont("DejaVuSans", reg))
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", bold))
        return "DejaVuSans", "DejaVuSans-Bold"
    except Exception:
        return "Helvetica", "Helvetica-Bold"


def _safe_max(arr, fallback=1.0):
    """np.nanmax tolerante a None y object dtype."""
    v = pd.to_numeric(np.array(arr).ravel(), errors="coerce")
    m = np.nanmax(v) if not np.all(np.isnan(v)) else fallback
    return m if np.isfinite(m) and m > 0 else fallback


def _make_table(df, font_reg, font_bold, font_size=6):
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    df_ = df.reset_index(drop=True).copy()
    # Format floats to 2 decimal places
    for col in df_.columns:
        if pd.api.types.is_float_dtype(df_[col]):
            df_[col] = df_[col].map(lambda x: f"{x:.2f}" if pd.notna(x) else "")
        else:
            df_[col] = df_[col].fillna("").astype(str)
    data = [list(map(str, df_.columns))] + [list(map(str, r)) for _, r in df_.iterrows()]
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME",       (0, 0), (-1,  0), font_bold),
        ("FONTNAME",       (0, 1), (-1, -1), font_reg),
        ("FONTSIZE",       (0, 0), (-1, -1), font_size),
        ("TEXTCOLOR",      (0, 0), (-1,  0), colors.whitesmoke),
        ("BACKGROUND",     (0, 0), (-1,  0), colors.HexColor("#1b3a6b")),
        ("ALIGN",          (0, 0), (-1,  0), "CENTER"),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",           (0, 0), (-1, -1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#f0f4ff")]),
        ("ROTATE",         (0, 0), (-1,  0), 90),
    ]))
    return t


def _fig_image(fig, doc, dpi=180, max_w_ratio=0.96, max_h_ratio=0.72):
    from reportlab.platypus import Image
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    w_in, h_in = fig.get_size_inches()
    plt.close(fig)
    buf.seek(0)
    w_pts, h_pts = w_in * 72, h_in * 72
    scale = min(doc.width * max_w_ratio / w_pts, doc.height * max_h_ratio / h_pts, 1.0)
    return Image(buf, width=w_pts * scale, height=h_pts * scale)


def _pct_vec(row, population):
    out = []
    for c in row.index:
        col_pop = population[c].dropna().values
        val = pd.to_numeric(row[c], errors='coerce')
        if len(col_pop) == 0 or pd.isna(val):
            out.append(np.nan)
        else:
            out.append((np.sum(col_pop <= val) / len(col_pop)) * 100.0)
    return pd.Series(out, index=row.index)


# ── Main entry point ──────────────────────────────────────────────

def generate_pdf(p1, p2, k=5, include_same=False, team="", pos="", nat="",
                 age_min=0, age_max=99, corr_pct=None):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    FONT_REG, FONT_BOLD = _register_fonts()
    dt = sim._df()

    for p in [p1, p2]:
        if p not in dt["Player"].values:
            raise ValueError(f"Player '{p}' not found.")

    # ── Compute top-K similars ──
    sim_result = sim.compute_similar(
        player=p1, team=team, pos=pos, nat=nat,
        age_min=age_min or 0, age_max=age_max or 99,
        k=k, include_same=include_same
    )
    top_rows = sim_result["similar"]

    basic_names = ["G","MP","FG","FGA","FG%","3P","3PA","3P%","2P","2PA","2P%","EFG%",
                   "FT","FTA","FT%","ORB","DRB","TRB","AST","STL","BLK","TOV","PF","PTS"]
    rate_cols  = sim._CACHE["rate_cols"]
    per36_cols = sim._CACHE["per36_cols"]
    stats_cols = sim._CACHE["stats_cols"]
    basic_cols = sim._present(dt, basic_names)

    roster = [p1] + [r["player"] for r in top_rows]
    uniq   = dt.drop_duplicates("Player").set_index("Player")
    team1  = uniq.loc[p1, "Team"] if p1 in uniq.index else ""
    team2  = uniq.loc[p2, "Team"] if p2 in uniq.index else ""
    c1, c2 = sim._pair_colors(team1, team2)

    pair = (dt[dt["Player"].isin([p1, p2])]
            .drop_duplicates("Player").set_index("Player").reindex([p1, p2]))

    # ── Build PDF ──
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=24, rightMargin=24,
                            topMargin=62, bottomMargin=34)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("CH3", parent=styles["Heading3"], alignment=TA_CENTER,
                              fontName=FONT_BOLD, fontSize=10))
    styles["Title"].fontName = FONT_BOLD
    styles["Normal"].fontSize = 8
    for st in styles.byName.values():
        st.fontName = FONT_REG

    on_page = _make_page_decorator(FONT_REG, FONT_BOLD)
    elems = []
    corr_str = f" — {corr_pct:.1f}% match" if corr_pct is not None else ""

    # ═══ PAGE 1: cover + top-K table + basic + advanced ═══
    elems.append(Paragraph(
        f"<para align='center'><b>Head-to-Head: {p1} vs {p2}{corr_str}</b></para>",
        styles["Title"]))
    elems.append(Spacer(1, 8))

    df_top = pd.DataFrame([{
        "Similar Player": r["player"], "Team": r["team"],
        "% Match": f"{r['correlation_pct']:.2f}%"
    } for r in top_rows])
    if not df_top.empty:
        elems.append(Paragraph("<b>Top similar players</b>", styles["CH3"]))
        elems.append(_make_table(df_top, FONT_REG, FONT_BOLD, font_size=7))
        elems.append(Spacer(1, 6))

    df_multi = (dt.loc[dt["Player"].isin(roster), ["Player", "Team3"] + basic_cols]
                .drop_duplicates("Player"))
    df_multi["_o"] = df_multi["Player"].map({p: i for i, p in enumerate(roster)})
    df_multi = df_multi.sort_values("_o").drop(columns="_o").rename(columns={"Team3": "Team"})
    elems.append(Paragraph("<b>Basic stats (group)</b>", styles["CH3"]))
    elems.append(_make_table(df_multi, FONT_REG, FONT_BOLD, font_size=5))
    elems.append(Spacer(1, 4))

    df_adv = (dt.loc[dt["Player"].isin(roster), ["Player", "Team3"] + stats_cols]
              .drop_duplicates("Player"))
    df_adv["_o"] = df_adv["Player"].map({p: i for i, p in enumerate(roster)})
    df_adv = df_adv.sort_values("_o").drop(columns="_o").rename(columns={"Team3": "Team"})
    for c in rate_cols + per36_cols:
        if c in df_adv.columns:
            df_adv[c] = pd.to_numeric(df_adv[c], errors="coerce").map(
                lambda x: f"{x:.2f}" if pd.notna(x) else "")
    elems.append(Paragraph("<b>Advanced stats (group)</b>", styles["CH3"]))
    elems.append(_make_table(df_adv, FONT_REG, FONT_BOLD, font_size=5))
    elems.append(PageBreak())

    # ═══ PAGE 2: Games+Min chart + Percentages chart ═══
    pal = [c1, c2]
    gm_cols = [c for c in sim._present(dt, ["G", "MP"]) if c in pair.columns]
    if gm_cols:
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.3))
        for i, c in enumerate(gm_cols[:2]):
            sub = pair[[c]].apply(pd.to_numeric, errors="coerce").T
            sub.index = [c.upper()]
            sub.plot(kind="bar", ax=axes[i], color=pal, legend=False)
            axes[i].set_title(c.upper())
            axes[i].set_ylim(0, _safe_max(sub.values) * 1.15)
            plt.sca(axes[i]); plt.xticks([])
        axes[-1].legend([p1, p2], loc="upper right")
        plt.tight_layout()
        elems.append(Paragraph("<b>Games & Minutes</b>", styles["CH3"]))
        elems.append(_fig_image(fig, doc, max_h_ratio=0.38))

    pct_cols = [c for c in sim._present(dt, ["FG%", "3P%", "2P%", "EFG%", "FT%", "TS%"])
                if c in pair.columns]
    if pct_cols:
        fig, ax = plt.subplots(figsize=(10, 3.2))
        sub = pair[pct_cols].apply(pd.to_numeric, errors="coerce").T
        sub.index = [c.upper() for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, 1.0); ax.legend([p1, p2]); plt.xticks(rotation=0); plt.tight_layout()
        elems.append(Paragraph("<b>Basic — Percentages</b>", styles["CH3"]))
        elems.append(_fig_image(fig, doc, max_h_ratio=0.44))
    elems.append(PageBreak())

    # ═══ PAGE 3: H2H tables + Per-game volumes ═══
    h2h_basic = pair[["Team3"] + basic_cols].rename(columns={"Team3": "Team"}).reset_index()
    elems.append(Paragraph(f"<b>H2H — {p1} vs {p2} (Basic)</b>", styles["CH3"]))
    elems.append(_make_table(h2h_basic, FONT_REG, FONT_BOLD, font_size=5))
    elems.append(Spacer(1, 4))

    h2h_adv = pair[["Team3"] + stats_cols].copy().rename(columns={"Team3": "Team"})
    for c in rate_cols + per36_cols:
        if c in h2h_adv.columns:
            h2h_adv[c] = pd.to_numeric(h2h_adv[c], errors="coerce").map(
                lambda x: f"{x:.2f}" if pd.notna(x) else "")
    elems.append(Paragraph(f"<b>H2H — {p1} vs {p2} (Advanced)</b>", styles["CH3"]))
    elems.append(_make_table(h2h_adv.reset_index(), FONT_REG, FONT_BOLD, font_size=5))
    elems.append(Spacer(1, 6))

    vol_targets = ["FG","FGA","3P","3PA","FT","FTA","TRB","AST","STL","BLK","TOV","PF","PTS"]
    vol_cols = [c for c in sim._present(dt, vol_targets) if c in pair.columns]
    if vol_cols:
        fig, ax = plt.subplots(figsize=(10.5, 4))
        sub = pair[vol_cols].apply(pd.to_numeric, errors="coerce").T
        sub.index = [c.upper() for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, _safe_max(sub.values) * 1.15)
        ax.legend([p1, p2]); plt.xticks(rotation=45, ha="right"); plt.tight_layout()
        elems.append(Paragraph("<b>Basic — Per-game volumes</b>", styles["CH3"]))
        elems.append(_fig_image(fig, doc, max_h_ratio=0.50))
    elems.append(PageBreak())

    # ═══ PAGE 4: Ratios + Per-36 ═══
    ratio_cols = [c for c in sim._present(dt, ["3PAR","FTR","TOV%_SHOOT"]) if c in pair.columns]
    if ratio_cols:
        fig, ax = plt.subplots(figsize=(9.5, 3.2))
        sub = pair[ratio_cols].apply(pd.to_numeric, errors="coerce").T
        sub.index = [c.upper() for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, 1.0); ax.legend([p1, p2]); plt.xticks(rotation=0); plt.tight_layout()
        elems.append(Paragraph("<b>Advanced — Ratios</b>", styles["CH3"]))
        elems.append(_fig_image(fig, doc, max_h_ratio=0.42))

    p36c = [c for c in per36_cols if c in pair.columns]
    if p36c:
        fig, ax = plt.subplots(figsize=(9.5, 3.2))
        sub = pair[p36c].apply(pd.to_numeric, errors="coerce").T
        sub.index = [c[:-7].upper() + "_P36" for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, _safe_max(sub.values) * 1.15)
        ax.legend([p1, p2]); plt.xticks(rotation=45, ha="right"); plt.tight_layout()
        elems.append(Paragraph("<b>Advanced — Per 36 minutes</b>", styles["CH3"]))
        elems.append(_fig_image(fig, doc, max_h_ratio=0.42))
    elems.append(PageBreak())

    # ═══ PAGE 5: Radar ═══
    radar_names = ["FG","FGA","3P","3PA","FT","FTA","TRB","STL","AST","TOV","BLK","PTS"]
    radar_cols  = [c for c in sim._present(dt, radar_names) if c in pair.columns and c in dt.columns]
    if radar_cols and len(radar_cols) >= 3:
        pop = dt[radar_cols].apply(pd.to_numeric, errors="coerce")
        pr1 = pair.loc[p1, radar_cols].apply(pd.to_numeric, errors="coerce")
        pr2 = pair.loc[p2, radar_cols].apply(pd.to_numeric, errors="coerce")
        vals1 = _pct_vec(pr1, pop).values.tolist()
        vals2 = _pct_vec(pr2, pop).values.tolist()
        labels = [c.upper() for c in radar_cols]
        vals1 += [vals1[0]]; vals2 += [vals2[0]]
        angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist() + [0]
        fig = plt.figure(figsize=(7.4, 7.4))
        ax  = plt.subplot(111, polar=True)
        ax.set_theta_offset(np.pi / 2); ax.set_theta_direction(-1)
        ax.set_facecolor("#f4f6fa")
        ax.set_xticks(angles[:-1], labels)
        ax.set_ylim(0, 100); ax.set_yticks([0, 20, 40, 60, 80, 100])
        l1, = ax.plot(angles, vals1, linewidth=2.3, color=c1, label=p1)
        ax.fill(angles, vals1, color=c1, alpha=0.25)
        l2, = ax.plot(angles, vals2, linewidth=2.3, color=c2, label=p2)
        ax.fill(angles, vals2, color=c2, alpha=0.25)
        ax.grid(color="gray", linestyle="dotted", alpha=0.5)
        fig.legend(handles=[l1, l2], loc="lower center", bbox_to_anchor=(0.5, -0.01),
                   ncol=2, frameon=False)
        plt.tight_layout()
        elems.append(Paragraph("<b>Radar — Global percentiles (0–100)</b>", styles["CH3"]))
        elems.append(_fig_image(fig, doc, max_h_ratio=0.70))

    doc.build(elems, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()
