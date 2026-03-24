from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.api.documents import router as documents_router
from app.api.search import router as search_router
from app.api.query import router as query_router
from app.api.answer import router as answer_router
from app.ui.routes import router as ui_router

app = FastAPI(title="Recall", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


app.include_router(documents_router)
app.include_router(search_router)
app.include_router(query_router)
app.include_router(answer_router)
app.include_router(ui_router)
app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")
