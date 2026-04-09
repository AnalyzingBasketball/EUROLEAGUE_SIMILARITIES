"""
pdf_gen.py — PDF report generation using ReportLab.
Generates a multi-page head-to-head comparison report.
"""
import io, unicodedata
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import similarity as sim


def _sanitize(text):
    norm = unicodedata.normalize("NFKD", str(text))
    return "".join(c if c.isalnum() else "_" for c in norm.encode("ascii","ignore").decode()).strip("_")


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


def _make_table(df, font_reg, font_bold, font_size=6):
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    df_ = df.reset_index(drop=True).fillna("").copy()
    data = [list(map(str, df_.columns))] + [list(map(str, r)) for _, r in df_.iterrows()]
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME",   (0,0), (-1,0),  font_bold),
        ("FONTNAME",   (0,1), (-1,-1), font_reg),
        ("FONTSIZE",   (0,0), (-1,-1), font_size),
        ("TEXTCOLOR",  (0,0), (-1,0),  colors.whitesmoke),
        ("BACKGROUND", (0,0), (-1,0),  colors.HexColor("#1b3a6b")),
        ("ALIGN",      (0,0), (-1,0),  "CENTER"),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("GRID",       (0,0), (-1,-1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.HexColor("#f0f4ff")]),
        ("ROTATE",     (0,0), (-1,0),  90),
    ]))
    return t


def _fig_image(fig, doc, dpi=180, max_w_ratio=0.96, max_h_ratio=0.72):
    from reportlab.platypus import Image
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    w_in, h_in = fig.get_size_inches()
    plt.close(fig)
    buf.seek(0)
    w_pts, h_pts = w_in*72, h_in*72
    scale = min(doc.width*max_w_ratio/w_pts, doc.height*max_h_ratio/h_pts, 1.0)
    return Image(buf, width=w_pts*scale, height=h_pts*scale)


def _pct_vec(row, population):
    out = []
    for c in row.index:
        col_pop = population[c].dropna().values
        if len(col_pop) == 0 or pd.isna(row[c]): out.append(np.nan)
        else: out.append((np.sum(col_pop <= row[c]) / len(col_pop)) * 100.0)
    return pd.Series(out, index=row.index)


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
                            leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("CH3", parent=styles["Heading3"], alignment=TA_CENTER,
                              fontName=FONT_BOLD, fontSize=10))
    styles["Title"].fontName = FONT_BOLD
    styles["Normal"].fontSize = 8
    for st in styles.byName.values(): st.fontName = FONT_REG

    elems = []
    corr_str = f" — {corr_pct:.1f}% match" if corr_pct is not None else ""

    # ═══ PAGE 1: cover + top-K table + basic + advanced ═══
    elems.append(Paragraph(
        f"<para align='center'><b>Head-to-Head: {p1} vs {p2}{corr_str}</b></para>",
        styles["Title"]))
    elems.append(Spacer(1, 8))

    df_top = pd.DataFrame([{
        "Similar Player": r["player"], "Team": r["team"],
        "% Match": f"{r['correlation_pct']:.3f}%"
    } for r in top_rows])
    if not df_top.empty:
        elems.append(Paragraph("<b>Top similar players</b>", styles["CH3"]))
        elems.append(_make_table(df_top, FONT_REG, FONT_BOLD, font_size=7))
        elems.append(Spacer(1, 6))

    # Multi-player basic
    df_multi = (dt.loc[dt["Player"].isin(roster),
                       ["Player","Team3"] + basic_cols]
                  .drop_duplicates("Player"))
    df_multi["_o"] = df_multi["Player"].map({p:i for i,p in enumerate(roster)})
    df_multi = df_multi.sort_values("_o").drop(columns="_o").rename(columns={"Team3":"Team"})
    elems.append(Paragraph("<b>Basic stats (group)</b>", styles["CH3"]))
    elems.append(_make_table(df_multi, FONT_REG, FONT_BOLD, font_size=5))
    elems.append(Spacer(1, 4))

    # Multi-player advanced
    df_adv = (dt.loc[dt["Player"].isin(roster),
                     ["Player","Team3"] + stats_cols]
                .drop_duplicates("Player"))
    df_adv["_o"] = df_adv["Player"].map({p:i for i,p in enumerate(roster)})
    df_adv = df_adv.sort_values("_o").drop(columns="_o").rename(columns={"Team3":"Team"})
    for c in rate_cols:
        if c in df_adv.columns: df_adv[c] = df_adv[c].map(lambda x: f"{x:.3f}" if pd.notna(x) else "")
    for c in per36_cols:
        if c in df_adv.columns: df_adv[c] = df_adv[c].map(lambda x: f"{x:.2f}" if pd.notna(x) else "")
    elems.append(Paragraph("<b>Advanced stats (group)</b>", styles["CH3"]))
    elems.append(_make_table(df_adv, FONT_REG, FONT_BOLD, font_size=5))
    elems.append(PageBreak())

    # ═══ PAGE 2: Games+Min chart + Percentages chart ═══
    pal = [c1, c2]
    gm_cols = [c for c in sim._present(dt, ["G","MP"]) if c in pair.columns]
    if gm_cols:
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.3))
        for i, c in enumerate(gm_cols[:2]):
            sub = pair[[c]].T; sub.index = [c.upper()]
            sub.plot(kind="bar", ax=axes[i], color=pal, legend=False)
            axes[i].set_title(c.upper()); axes[i].set_ylim(0, sub.values.max()*1.15 if sub.size else 1)
            plt.sca(axes[i]); plt.xticks([])
        axes[-1].legend([p1, p2], loc="upper right")
        plt.tight_layout()
        elems.append(Paragraph("<b>Games & Minutes</b>", styles["CH3"]))
        elems.append(_fig_image(fig, doc, max_h_ratio=0.38))

    pct_cols = [c for c in sim._present(dt, ["FG%","3P%","2P%","EFG%","FT%","TS%"]) if c in pair.columns]
    if pct_cols:
        fig, ax = plt.subplots(figsize=(10, 3.2))
        sub = pair[pct_cols].T; sub.index = [c.upper() for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, 1.0); ax.legend([p1, p2]); plt.xticks(rotation=0); plt.tight_layout()
        elems.append(Paragraph("<b>Basic — Percentages</b>", styles["CH3"]))
        elems.append(_fig_image(fig, doc, max_h_ratio=0.44))
    elems.append(PageBreak())

    # ═══ PAGE 3: H2H tables + Per-game volumes ═══
    h2h_basic = (pair[["Team3"] + basic_cols].rename(columns={"Team3":"Team"})).reset_index()
    elems.append(Paragraph(f"<b>H2H — {p1} vs {p2} (Basic)</b>", styles["CH3"]))
    elems.append(_make_table(h2h_basic, FONT_REG, FONT_BOLD, font_size=5))
    elems.append(Spacer(1, 4))

    h2h_adv = pair[["Team3"] + stats_cols].copy().rename(columns={"Team3":"Team"})
    for c in rate_cols:
        if c in h2h_adv.columns: h2h_adv[c] = h2h_adv[c].map(lambda x: f"{x:.3f}" if pd.notna(x) else "")
    for c in per36_cols:
        if c in h2h_adv.columns: h2h_adv[c] = h2h_adv[c].map(lambda x: f"{x:.2f}" if pd.notna(x) else "")
    elems.append(Paragraph(f"<b>H2H — {p1} vs {p2} (Advanced)</b>", styles["CH3"]))
    elems.append(_make_table(h2h_adv.reset_index(), FONT_REG, FONT_BOLD, font_size=5))
    elems.append(Spacer(1, 6))

    vol_targets = ["FG","FGA","3P","3PA","FT","FTA","TRB","AST","STL","BLK","TOV","PF","PTS"]
    vol_cols = [c for c in sim._present(dt, vol_targets) if c in pair.columns]
    if vol_cols:
        fig, ax = plt.subplots(figsize=(10.5, 4))
        sub = pair[vol_cols].T; sub.index = [c.upper() for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, sub.values.max()*1.15 if sub.size else 1)
        ax.legend([p1, p2]); plt.xticks(rotation=45, ha="right"); plt.tight_layout()
        elems.append(Paragraph("<b>Basic — Per-game volumes</b>", styles["CH3"]))
        elems.append(_fig_image(fig, doc, max_h_ratio=0.50))
    elems.append(PageBreak())

    # ═══ PAGE 4: Ratios + Per-36 ═══
    ratio_cols = [c for c in sim._present(dt, ["3PAR","FTR","TOV%_SHOOT"]) if c in pair.columns]
    if ratio_cols:
        fig, ax = plt.subplots(figsize=(9.5, 3.2))
        sub = pair[ratio_cols].T; sub.index = [c.upper() for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, 1.0); ax.legend([p1, p2]); plt.xticks(rotation=0); plt.tight_layout()
        elems.append(Paragraph("<b>Advanced — Ratios</b>", styles["CH3"]))
        elems.append(_fig_image(fig, doc, max_h_ratio=0.42))

    p36c = [c for c in per36_cols if c in pair.columns]
    if p36c:
        fig, ax = plt.subplots(figsize=(9.5, 3.2))
        sub = pair[p36c].T; sub.index = [c[:-7].upper()+"_P36" for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, sub.values.max()*1.15 if sub.size else 1)
        ax.legend([p1, p2]); plt.xticks(rotation=45, ha="right"); plt.tight_layout()
        elems.append(Paragraph("<b>Advanced — Per 36 minutes</b>", styles["CH3"]))
        elems.append(_fig_image(fig, doc, max_h_ratio=0.42))
    elems.append(PageBreak())

    # ═══ PAGE 5: Radar ═══
    radar_names = ["FG","FGA","3P","3PA","FT","FTA","TRB","STL","AST","TOV","BLK","PTS"]
    radar_cols  = [c for c in sim._present(dt, radar_names) if c in pair.columns and c in dt.columns]
    if radar_cols and len(radar_cols) >= 3:
        pop = dt[radar_cols]
        vals1 = _pct_vec(pair.loc[p1, radar_cols], pop).values.tolist()
        vals2 = _pct_vec(pair.loc[p2, radar_cols], pop).values.tolist()
        labels = [c.upper() for c in radar_cols]
        vals1 += [vals1[0]]; vals2 += [vals2[0]]
        angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist() + [0]
        fig = plt.figure(figsize=(7.4, 7.4))
        ax  = plt.subplot(111, polar=True)
        ax.set_theta_offset(np.pi/2); ax.set_theta_direction(-1)
        ax.set_facecolor("#f4f6fa")
        ax.set_xticks(angles[:-1], labels)
        ax.set_ylim(0, 100); ax.set_yticks([0,20,40,60,80,100])
        l1, = ax.plot(angles, vals1, linewidth=2.3, color=c1, label=p1)
        ax.fill(angles, vals1, color=c1, alpha=0.25)
        l2, = ax.plot(angles, vals2, linewidth=2.3, color=c2, label=p2)
        ax.fill(angles, vals2, color=c2, alpha=0.25)
        ax.grid(color="gray", linestyle="dotted", alpha=0.5)
        fig.legend(handles=[l1,l2], loc="lower center", bbox_to_anchor=(0.5, -0.01),
                   ncol=2, frameon=False)
        plt.tight_layout()
        elems.append(Paragraph("<b>Radar — Global percentiles (0–100)</b>", styles["CH3"]))
        elems.append(_fig_image(fig, doc, max_h_ratio=0.70))

    doc.build(elems)
    return buf.getvalue()
