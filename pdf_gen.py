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

def _load_png(key, filename):
    """Carga un PNG desde assets/ con caché. Devuelve BytesIO o None."""
    if key in _LOGO_CACHE:
        _LOGO_CACHE[key].seek(0)
        return _LOGO_CACHE[key]
    path = os.path.join(_ASSETS, filename)
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = f.read()
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            buf = io.BytesIO(data)
            _LOGO_CACHE[key] = buf
            return buf
    return None


def _el_logo_buf():
    # 1) PNG incluido en el repo (assets/euroleague_logo.png)
    buf = _load_png("el", "euroleague_logo.png")
    if buf:
        return buf
    # 2) Fallback: badge matplotlib
    buf = _gen_el_badge()
    _LOGO_CACHE["el"] = buf
    return buf


def _ab_logo_buf():
    # 1) PNG incluido en el repo (assets/ab_logo.png)
    buf = _load_png("ab", "ab_logo.png")
    if buf:
        return buf
    # 2) Fallback: badge matplotlib
    buf = _gen_ab_badge()
    _LOGO_CACHE["ab"] = buf
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
    """
    Recreación del logo Analyzing Basketball.
    Fondo blanco con icono basket+datos y texto corporativo oscuro.
    Se coloca sobre una píldora blanca en la franja azul del header.
    """
    from matplotlib.patches import Circle, Arc, FancyArrowPatch
    import matplotlib.lines as mlines

    fig, ax = plt.subplots(figsize=(2.6, 0.90))
    ax.set_xlim(0, 2.6); ax.set_ylim(0, 0.90)
    ax.set_aspect("equal"); ax.axis("off")
    fig.patch.set_facecolor("white")

    # ── Balón de baloncesto ──────────────────────────────────────
    cx, cy, r = 0.45, 0.45, 0.36
    ax.add_patch(Circle((cx, cy), r, color="#e8740c", zorder=2))
    # Costuras (líneas negras curvas simplificadas)
    ax.plot([cx, cx], [cy - r + 0.03, cy + r - 0.03], color="#1a1a2e", lw=1.4, zorder=3)
    ax.plot([cx - r + 0.03, cx + r - 0.03], [cy, cy], color="#1a1a2e", lw=1.4, zorder=3)
    ax.add_patch(Arc((cx - 0.18, cy), 0.36, 0.52,
                     angle=0, theta1=-90, theta2=90, color="#1a1a2e", lw=1.2, zorder=3))
    ax.add_patch(Arc((cx + 0.18, cy), 0.36, 0.52,
                     angle=0, theta1=90, theta2=270, color="#1a1a2e", lw=1.2, zorder=3))

    # ── Arco de datos (azul claro, parcial) ─────────────────────
    ax.add_patch(Arc((cx, cy), 0.88, 0.88,
                     angle=0, theta1=20, theta2=160, color="#0047ff", lw=2.0, zorder=1))

    # ── Mini barras de estadística ───────────────────────────────
    bars_x = [0.90, 0.98, 1.06, 1.14, 1.22]
    bars_h = [0.25, 0.42, 0.35, 0.55, 0.30]
    bar_colors = ["#aaaaaa", "#aaaaaa", "#ff6b1a", "#aaaaaa", "#aaaaaa"]
    for bx, bh, bc in zip(bars_x, bars_h, bar_colors):
        ax.add_patch(plt.Rectangle((bx - 0.025, 0.10), 0.05, bh,
                                   color=bc, zorder=1))

    # ── Texto corporativo ────────────────────────────────────────
    ax.text(1.32, 0.62, "ANALYZING", ha="left", va="center",
            fontsize=7.8, fontweight="bold", color="#1a1a2e")
    ax.text(1.32, 0.40, "BASKETBALL", ha="left", va="center",
            fontsize=7.8, fontweight="bold", color="#1a1a2e")
    ax.text(1.32, 0.18, "DATA  INTELLIGENCE", ha="left", va="center",
            fontsize=4.8, color="#555555", letterspacing=0.5)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=180, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


# ── Header / footer decorator ─────────────────────────────────────

def _make_page_decorator(fr, fb):
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader

    PW, PH   = landscape(A4)
    HDR_H    = 46          # altura franja superior
    FTR_H    = 22          # altura franja inferior
    PAD      = 5           # padding interior logos
    BLUE     = colors.HexColor("#0047ff")
    WHITE    = colors.white

    def on_page(canvas, doc):
        canvas.saveState()

        # ═══ FRANJA SUPERIOR ══════════════════════════════════════
        canvas.setFillColor(BLUE)
        canvas.rect(0, PH - HDR_H, PW, HDR_H, fill=1, stroke=0)

        # Logo AB — píldora blanca + logo real
        try:
            ab = _ab_logo_buf(); ab.seek(0)
            ir = ImageReader(ab); iw, ih = ir.getSize()
            inner_h = HDR_H - 2 * PAD
            scale = min(inner_h * 4.0 / iw, inner_h / ih)
            img_w = iw * scale; img_h = ih * scale
            img_x = PAD + 6
            img_y = PH - HDR_H + (HDR_H - img_h) / 2
            # Fondo blanco redondeado
            canvas.setFillColor(WHITE)
            canvas.roundRect(img_x - 4, img_y - 3,
                             img_w + 8, img_h + 6, 5, fill=1, stroke=0)
            canvas.drawImage(ir, img_x, img_y,
                             width=img_w, height=img_h, mask="auto")
        except Exception:
            canvas.setFont(fb, 9)
            canvas.setFillColor(WHITE)
            canvas.drawString(PAD + 4, PH - HDR_H / 2 - 4, "Analyzing Basketball")

        # Logo EuroLeague — esquina superior derecha con píldora blanca
        try:
            el = _el_logo_buf(); el.seek(0)
            ir = ImageReader(el); iw, ih = ir.getSize()
            # Ajustar a la altura disponible de la franja
            target_h = HDR_H - 6   # casi toda la franja
            scale    = target_h / ih
            img_w    = iw * scale
            img_h    = ih * scale
            img_x    = PW - PAD - 6 - img_w
            img_y    = PH - HDR_H + (HDR_H - img_h) / 2
            # Fondo blanco redondeado
            canvas.setFillColor(WHITE)
            canvas.roundRect(img_x - 4, img_y - 3,
                             img_w + 8, img_h + 6, 5, fill=1, stroke=0)
            # Sin mask="auto" — la píldora blanca ya hace de fondo
            canvas.drawImage(ir, img_x, img_y,
                             width=img_w, height=img_h)
        except Exception as _e:
            canvas.setFont(fb, 9)
            canvas.setFillColor(WHITE)
            canvas.drawRightString(PW - PAD - 6, PH - HDR_H / 2 - 4, "EuroLeague")

        # Texto central en la franja (blanco)
        canvas.setFont(fb, 9)
        canvas.setFillColor(WHITE)
        canvas.drawCentredString(PW / 2, PH - HDR_H + HDR_H * 0.60,
                                 "EUROLEAGUE · SIMILARITY EXPLORER")
        canvas.setFont(fr, 6.5)
        canvas.setFillColor(colors.HexColor("#ccd8ff"))
        canvas.drawCentredString(PW / 2, PH - HDR_H + HDR_H * 0.28,
                                 "EuroLeague Stats · 2025/26")

        # ═══ FRANJA INFERIOR ══════════════════════════════════════
        canvas.setFillColor(BLUE)
        canvas.rect(0, 0, PW, FTR_H, fill=1, stroke=0)

        canvas.setFont(fr, 6.5)
        canvas.setFillColor(WHITE)
        canvas.drawCentredString(
            PW / 2, FTR_H / 2 - 2,
            f"© 2026 Analyzing Basketball  |  www.analyzingbasketball.com"
        )
        canvas.setFont(fr, 6)
        canvas.setFillColor(colors.HexColor("#ccd8ff"))
        canvas.drawRightString(PW - PAD - 4, FTR_H / 2 - 2,
                               f"Página {doc.page}")

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


def _make_table(df, font_reg, font_bold, font_size=6, doc_width=794):
    """
    Construye una Table de ReportLab ajustada a doc_width.
    - Columnas de texto (Player, Team…) reciben ancho fijo generoso.
    - El resto se reparte equitativamente en el ancho sobrante.
    - Si el ancho libre < 12 pts, reduce font_size automáticamente.
    """
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors

    df_ = df.reset_index(drop=True).copy()
    for col in df_.columns:
        if pd.api.types.is_float_dtype(df_[col]):
            df_[col] = df_[col].map(lambda x: f"{x:.2f}" if pd.notna(x) else "")
        else:
            df_[col] = df_[col].fillna("").astype(str)

    # Columnas de texto con ancho fijo
    FIXED_W = {
        "player":         80,
        "similar player": 130,
        "team":            32,   # Team3 abbreviation en tablas de stats
        "club":           190,   # nombre completo en tabla top-K
        "team3":           32,
        "min/g":           36,   # minutos por partido
        "% match":         52,
        "role":            44,
        "pos":             16,
    }
    cols = list(df_.columns)
    n    = len(cols)
    fixed = {}
    for i, c in enumerate(cols):
        w = FIXED_W.get(str(c).lower().strip())
        if w:
            fixed[i] = w

    fixed_total = sum(fixed.values())
    n_free = n - len(fixed)

    if n_free > 0:
        free_w = (doc_width - fixed_total) / n_free
        # Si las columnas numéricas son muy estrechas, achica la fuente
        if free_w < 12 and font_size > 4:
            font_size = max(4, font_size - 1)
            free_w = (doc_width - fixed_total) / n_free
        free_w = max(11, free_w)
    else:
        free_w = 20

    col_widths = [fixed.get(i, free_w) for i in range(n)]

    data = [list(map(str, df_.columns))] + [list(map(str, r)) for _, r in df_.iterrows()]
    t = Table(data, repeatRows=1, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("FONTNAME",       (0, 0), (-1,  0), font_bold),
        ("FONTNAME",       (0, 1), (-1, -1), font_reg),
        ("FONTSIZE",       (0, 0), (-1, -1), font_size),
        ("LEADING",        (0, 0), (-1, -1), font_size + 1),
        ("TEXTCOLOR",      (0, 0), (-1,  0), colors.whitesmoke),
        ("BACKGROUND",     (0, 0), (-1,  0), colors.HexColor("#0047ff")),
        ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
        ("ALIGN",          (0, 1), (1,  -1), "LEFT"),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",           (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f0f4ff")]),
        ("TOPPADDING",     (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 1),
        ("LEFTPADDING",    (0, 0), (-1, -1), 2),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 2),
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


def _drop_empty_cols(df):
    """Elimina columnas donde TODOS los valores son cadena vacía o NaN."""
    keep = []
    for c in df.columns:
        col = df[c].replace("", np.nan)
        if col.notna().any():
            keep.append(c)
    return df[keep]


# ── Main entry point ──────────────────────────────────────────────

def generate_pdf(p1, p2, k=5, include_same=False, team="", pos="", nat="",
                 age_min=0, age_max=99, mp_min=0, corr_pct=None):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether
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
        mp_min=mp_min or 0, k=k, include_same=include_same
    )
    top_rows = sim_result["similar"]

    basic_names_A = ["G","MP","FG","FGA","FG%","3P","3PA","3P%","2P","2PA","2P%","EFG%"]
    basic_names_B = ["FT","FTA","FT%","ORB","DRB","TRB","AST","STL","BLK","TOV","PF","PTS"]
    rate_cols  = sim._CACHE["rate_cols"]
    per36_cols = sim._CACHE["per36_cols"]
    stats_cols = sim._CACHE["stats_cols"]
    basic_cols_A = sim._present(dt, basic_names_A)
    basic_cols_B = sim._present(dt, basic_names_B)
    basic_cols   = basic_cols_A + basic_cols_B   # lista completa (gráficos)

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
                            topMargin=58, bottomMargin=30)
    DOC_W = int(landscape(A4)[0]) - 48   # 794 pts disponibles
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
        "Similar Player": r["player"],
        "Club":           r["team"],
        "Min/G":          f"{r['mp']:.1f}" if r.get("mp") is not None else "-",
        "% Match":        f"{r['correlation_pct']:.2f}%"
    } for r in top_rows])
    if not df_top.empty:
        elems.append(Paragraph("<b>Top similar players</b>", styles["CH3"]))
        elems.append(_make_table(df_top, FONT_REG, FONT_BOLD, font_size=9,
                                 doc_width=DOC_W))
        elems.append(Spacer(1, 8))

    def _basic_group_df(cols_subset):
        d = (dt.loc[dt["Player"].isin(roster), ["Player", "Team3"] + cols_subset]
             .drop_duplicates("Player"))
        d["_o"] = d["Player"].map({p: i for i, p in enumerate(roster)})
        d = d.sort_values("_o").drop(columns="_o").rename(columns={"Team3": "Team"})
        return _drop_empty_cols(d)

    elems.append(Paragraph("<b>Basic stats — Shooting (group)</b>", styles["CH3"]))
    elems.append(_make_table(_basic_group_df(basic_cols_A), FONT_REG, FONT_BOLD,
                             font_size=7, doc_width=DOC_W))
    elems.append(Spacer(1, 8))
    elems.append(Paragraph("<b>Basic stats — Rebounds, Defense & Production (group)</b>", styles["CH3"]))
    elems.append(_make_table(_basic_group_df(basic_cols_B), FONT_REG, FONT_BOLD,
                             font_size=7, doc_width=DOC_W))
    elems.append(PageBreak())

    # Advanced stats: dividir en dos bloques para que quepan en A4
    adv_cols_A = [c for c in (rate_cols + sim._present(dt, ["ORB%","DRB%","REB%","AST%","TOV%","A2T","GS%","WIN%"])) if c in dt.columns]
    adv_cols_B = [c for c in (per36_cols + sim._present(dt, ["PTS_2P%","PTS_3P%","PTS_FT%","2PA_SH","3PA_SH","2PT_R","3PT_R"])) if c in dt.columns]

    def _adv_df(cols_subset):
        d = (dt.loc[dt["Player"].isin(roster), ["Player", "Team3"] + cols_subset]
             .drop_duplicates("Player"))
        d["_o"] = d["Player"].map({p: i for i, p in enumerate(roster)})
        d = d.sort_values("_o").drop(columns="_o").rename(columns={"Team3": "Team"})
        for c in cols_subset:
            if c in d.columns:
                d[c] = pd.to_numeric(d[c], errors="coerce").map(
                    lambda x: f"{x:.2f}" if pd.notna(x) else "")
        return _drop_empty_cols(d)

    if adv_cols_A:
        elems.append(Paragraph("<b>Advanced stats — Rates & Percentages (group)</b>", styles["CH3"]))
        elems.append(_make_table(_adv_df(adv_cols_A), FONT_REG, FONT_BOLD, font_size=7, doc_width=DOC_W))
        elems.append(Spacer(1, 8))
    if adv_cols_B:
        elems.append(Paragraph("<b>Advanced stats — Per 36 & Scoring (group)</b>", styles["CH3"]))
        elems.append(_make_table(_adv_df(adv_cols_B), FONT_REG, FONT_BOLD, font_size=7, doc_width=DOC_W))
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
        elems.append(KeepTogether([
            Paragraph("<b>Games & Minutes</b>", styles["CH3"]),
            _fig_image(fig, doc, max_h_ratio=0.38),
        ]))

    pct_cols = [c for c in sim._present(dt, ["FG%", "3P%", "2P%", "EFG%", "FT%", "TS%"])
                if c in pair.columns]
    if pct_cols:
        fig, ax = plt.subplots(figsize=(10, 3.2))
        sub = pair[pct_cols].apply(pd.to_numeric, errors="coerce").T
        sub.index = [c.upper() for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, 1.0); ax.legend([p1, p2]); plt.xticks(rotation=0); plt.tight_layout()
        elems.append(KeepTogether([
            Paragraph("<b>Basic — Percentages</b>", styles["CH3"]),
            _fig_image(fig, doc, max_h_ratio=0.44),
        ]))
    elems.append(PageBreak())

    # ═══ PAGE 3: H2H tables + Per-game volumes ═══
    def _h2h_basic_df(cols_subset):
        d = (pair[["Team3"] + [c for c in cols_subset if c in pair.columns]]
             .rename(columns={"Team3": "Team"}).reset_index())
        return _drop_empty_cols(d)

    elems.append(Paragraph(f"<b>H2H — {p1} vs {p2} (Basic — Shooting)</b>", styles["CH3"]))
    elems.append(_make_table(_h2h_basic_df(basic_cols_A), FONT_REG, FONT_BOLD,
                             font_size=7, doc_width=DOC_W))
    elems.append(Spacer(1, 8))
    elems.append(Paragraph(f"<b>H2H — {p1} vs {p2} (Basic — Rebounds, Defense & Production)</b>", styles["CH3"]))
    elems.append(_make_table(_h2h_basic_df(basic_cols_B), FONT_REG, FONT_BOLD,
                             font_size=7, doc_width=DOC_W))
    elems.append(Spacer(1, 8))

    # H2H Advanced — dividir igual que el grupo
    if adv_cols_A:
        h2h_adv_A = pair[["Team3"] + [c for c in adv_cols_A if c in pair.columns]].copy().rename(columns={"Team3": "Team"})
        for c in adv_cols_A:
            if c in h2h_adv_A.columns:
                h2h_adv_A[c] = pd.to_numeric(h2h_adv_A[c], errors="coerce").map(
                    lambda x: f"{x:.2f}" if pd.notna(x) else "")
        h2h_adv_A = _drop_empty_cols(h2h_adv_A.reset_index())
        elems.append(Paragraph(f"<b>H2H — {p1} vs {p2} (Advanced Rates)</b>", styles["CH3"]))
        elems.append(_make_table(h2h_adv_A, FONT_REG, FONT_BOLD, font_size=7, doc_width=DOC_W))
        elems.append(Spacer(1, 8))
    if adv_cols_B:
        h2h_adv_B = pair[["Team3"] + [c for c in adv_cols_B if c in pair.columns]].copy().rename(columns={"Team3": "Team"})
        for c in adv_cols_B:
            if c in h2h_adv_B.columns:
                h2h_adv_B[c] = pd.to_numeric(h2h_adv_B[c], errors="coerce").map(
                    lambda x: f"{x:.2f}" if pd.notna(x) else "")
        h2h_adv_B = _drop_empty_cols(h2h_adv_B.reset_index())
        elems.append(Paragraph(f"<b>H2H — {p1} vs {p2} (Per 36 & Scoring)</b>", styles["CH3"]))
        elems.append(_make_table(h2h_adv_B, FONT_REG, FONT_BOLD, font_size=7, doc_width=DOC_W))
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
        elems.append(KeepTogether([
            Paragraph("<b>Basic — Per-game volumes</b>", styles["CH3"]),
            _fig_image(fig, doc, max_h_ratio=0.50),
        ]))
    elems.append(PageBreak())

    # ═══ PAGE 4: Ratios + Per-36 ═══
    ratio_cols = [c for c in sim._present(dt, ["3PAR","FTR","TOV%_SHOOT"]) if c in pair.columns]
    if ratio_cols:
        fig, ax = plt.subplots(figsize=(9.5, 3.2))
        sub = pair[ratio_cols].apply(pd.to_numeric, errors="coerce").T
        sub.index = [c.upper() for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, 1.0); ax.legend([p1, p2]); plt.xticks(rotation=0); plt.tight_layout()
        elems.append(KeepTogether([
            Paragraph("<b>Advanced — Ratios</b>", styles["CH3"]),
            _fig_image(fig, doc, max_h_ratio=0.42),
        ]))

    p36c = [c for c in per36_cols if c in pair.columns]
    if p36c:
        fig, ax = plt.subplots(figsize=(9.5, 3.2))
        sub = pair[p36c].apply(pd.to_numeric, errors="coerce").T
        sub.index = [c[:-7].upper() + "_P36" for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, _safe_max(sub.values) * 1.15)
        ax.legend([p1, p2]); plt.xticks(rotation=45, ha="right"); plt.tight_layout()
        elems.append(KeepTogether([
            Paragraph("<b>Advanced — Per 36 minutes</b>", styles["CH3"]),
            _fig_image(fig, doc, max_h_ratio=0.42),
        ]))
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
        elems.append(KeepTogether([
            Paragraph("<b>Radar — Global percentiles (0–100)</b>", styles["CH3"]),
            _fig_image(fig, doc, max_h_ratio=0.70),
        ]))

    doc.build(elems, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()
