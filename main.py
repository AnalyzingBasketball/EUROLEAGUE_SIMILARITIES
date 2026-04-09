"""
main.py — FastAPI application for the Euroleague Similarity Explorer.
Designed for deployment on HuggingFace Docker Spaces.
"""
import io, os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import similarity as sim
import pdf_gen

app = FastAPI(title="Euroleague Similarity Explorer", version="1.0.0")

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
    age_min: int = Query(default=0),
    age_max: int = Query(default=99),
):
    sim.load_data()
    return sim.get_filter_options(team=team, pos=pos, nat=nat,
                                  age_min=age_min, age_max=age_max)


@app.get("/api/similar")
def api_similar(
    player: str  = Query(...),
    team:   str  = Query(default=""),
    pos:    str  = Query(default=""),
    nat:    str  = Query(default=""),
    age_min: int = Query(default=0),
    age_max: int = Query(default=99),
    k:       int = Query(default=5, ge=1, le=20),
    include_same: bool = Query(default=False),
):
    sim.load_data()
    try:
        return sim.compute_similar(
            player=player, team=team, pos=pos, nat=nat,
            age_min=age_min, age_max=age_max, k=k, include_same=include_same,
        )
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
    team:     str = Query(default=""),
    pos:      str = Query(default=""),
    nat:      str = Query(default=""),
    age_min:  int = Query(default=0),
    age_max:  int = Query(default=99),
    corr_pct: float = Query(default=None),
):
    sim.load_data()
    try:
        pdf_bytes = pdf_gen.generate_pdf(
            p1=p1, p2=p2, k=k, include_same=include_same,
            team=team, pos=pos, nat=nat,
            age_min=age_min, age_max=age_max, corr_pct=corr_pct,
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
