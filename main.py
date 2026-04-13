"""
main.py — FastAPI application for the Euroleague Similarity Explorer.
Designed for deployment on HuggingFace Docker Spaces.
"""
import io, os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

import similarity as sim
import pdf_gen

app = FastAPI(title="Euroleague Similarity Explorer", version="1.0.0")

if os.path.isdir("assets"):
    app.mount("/assets", StaticFiles(directory="assets"), name="assets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    sim.load_data()


@app.get("/", response_class=HTMLResponse)
def root():
    with open("frontend.html", encoding="utf-8") as f:
        return f.read()


@app.get("/api/players")
def api_players(
    team: str = Query(default=""),
    pos:  str = Query(default=""),
    nat:  str = Query(default=""),
    age_min:    int   = Query(default=0),
    age_max:    int   = Query(default=99),
    height_min: int   = Query(default=0),
    height_max: int   = Query(default=999),
    mp_min:     float = Query(default=0),
):
    sim.load_data()
    return sim.get_filter_options(team=team, pos=pos, nat=nat,
                                  age_min=age_min, age_max=age_max,
                                  height_min=height_min, height_max=height_max,
                                  mp_min=mp_min)


@app.get("/api/similar")
def api_similar(
    player: str  = Query(...),
    team:   str  = Query(default=""),
    pos:    str  = Query(default=""),
    nat:    str  = Query(default=""),
    age_min:    int   = Query(default=0),
    age_max:    int   = Query(default=99),
    height_min: int   = Query(default=0),
    height_max: int   = Query(default=999),
    mp_min:     float = Query(default=0),
    k:          int   = Query(default=5, ge=1, le=20),
    include_same: bool = Query(default=False),
):
    sim.load_data()
    try:
        return sim.compute_similar(
            player=player, team=team, pos=pos, nat=nat,
            age_min=age_min, age_max=age_max,
            height_min=height_min, height_max=height_max,
            mp_min=mp_min, k=k, include_same=include_same,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
def api_stats(
    p1: str = Query(...),
    p2: str = Query(...),
):
    sim.load_data()
    try:
        return sim.get_player_stats(p1, p2)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/correlation")
def api_correlation(
    p1: str = Query(...),
    p2: str = Query(...),
):
    sim.load_data()
    try:
        pct = sim.get_correlation(p1, p2)
        return {"p1": p1, "p2": p2, "correlation_pct": pct}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/charts")
def api_charts(
    p1: str = Query(...),
    p2: str = Query(...),
):
    sim.load_data()
    try:
        return sim.generate_charts(p1, p2)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pdf")
def api_pdf(
    p1: str   = Query(...),
    p2: str   = Query(...),
    k:  int   = Query(default=5),
    include_same: bool  = Query(default=False),
    team:     str   = Query(default=""),
    pos:      str   = Query(default=""),
    nat:      str   = Query(default=""),
    age_min:  int   = Query(default=0),
    age_max:  int   = Query(default=99),
    mp_min:   float = Query(default=0),
    corr_pct: float = Query(default=None),
):
    sim.load_data()
    try:
        pdf_bytes = pdf_gen.generate_pdf(
            p1=p1, p2=p2, k=k, include_same=include_same,
            team=team, pos=pos, nat=nat,
            age_min=age_min, age_max=age_max,
            mp_min=mp_min, corr_pct=corr_pct,
        )
        p1s = p1.replace(" ", "_"); p2s = p2.replace(" ", "_")
        filename = f"Comparison_{p1s}_vs_{p2s}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/shotchart")
def api_shotchart(player: str = Query(...)):
    try:
        return sim.get_player_shots(player)
    except Exception as e:
        return JSONResponse(content={"shots": [], "total_shots": 0, "made": 0, "missed": 0, "fg_pct": 0.0})


@app.get("/api/shotdebug")
def api_shotdebug():
    """Diagnostic endpoint — remove after debugging."""
    import requests as _req
    out = {}
    # 1. Test Results endpoint for gamecodes
    try:
        r = _req.get("https://live.euroleague.net/api/Results",
                     params={"seasonCode": "E2025"}, timeout=15)
        out["results_status"] = r.status_code
        data = r.json()
        rows = data if isinstance(data, list) else data.get("Rows", data.get("rows", []))
        out["results_rows_count"] = len(rows)
        out["results_first_row_keys"] = list(rows[0].keys()) if rows else []
        out["results_first_row"] = rows[0] if rows else {}
    except Exception as e:
        out["results_error"] = str(e)
    # 2. Test Points endpoint for game 1
    try:
        r2 = _req.get("https://live.euroleague.net/api/Points",
                      params={"gamecode": 1, "seasoncode": "E2025"}, timeout=15)
        out["points_status"] = r2.status_code
        data2 = r2.json()
        rows2 = data2.get("Rows", data2.get("rows", []))
        out["points_rows_count"] = len(rows2)
        out["points_first_row_keys"] = list(rows2[0].keys()) if rows2 else []
        out["points_first_row"] = rows2[0] if rows2 else {}
    except Exception as e:
        out["points_error"] = str(e)
    # 3. Show a few player codes from the main dataframe
    try:
        dt = sim._df()
        code_col = sim._find_col(dt, ["Code", "code"])
        out["code_col_name"] = code_col
        out["sample_player_codes"] = dt[[dt.columns[0], code_col]].head(3).values.tolist() if code_col else []
    except Exception as e:
        out["df_error"] = str(e)
    return out


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
