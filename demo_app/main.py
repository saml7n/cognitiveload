from fastapi import FastAPI
from demo_app.api.routes import router

app = FastAPI(title="FinServ Ledger API")

app.include_router(router)
