"""FastAPI app — ingress, cases, approvals, audit. Routers are added
incrementally as each build step lands (see docs/architecture.md §8)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.routers import approvals, audit, cases, ingress

app = FastAPI(
    title="Agentic FinOps Assistant API",
    description="Ingress, orchestration, approvals, and audit for the Agentic Financial Operations Assistant.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingress.router)
app.include_router(audit.router)
app.include_router(cases.router)
app.include_router(approvals.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
