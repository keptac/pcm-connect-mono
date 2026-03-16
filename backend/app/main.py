from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.routes import academic_programs, admin, analytics, auth, broadcasts, conferences, events, funding, mandatory_programs, marketplace, members, messages, program_updates, programs, reporting_periods, reports, unions, universities, users
from .core.config import settings
from .startup import init as init_data

app = FastAPI(title=settings.app_name)
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

app.include_router(auth.router)
app.include_router(universities.router)
app.include_router(unions.router)
app.include_router(conferences.router)
app.include_router(programs.router)
app.include_router(academic_programs.router)
app.include_router(users.router)
app.include_router(members.router)
app.include_router(broadcasts.router)
app.include_router(messages.router)
app.include_router(marketplace.router)
app.include_router(events.router)
app.include_router(mandatory_programs.router)
app.include_router(reporting_periods.router)
app.include_router(program_updates.router)
app.include_router(funding.router)
app.include_router(reports.router)
app.include_router(analytics.router)
app.include_router(admin.router)


@app.on_event("startup")
def startup_event():
    init_data()


@app.get("/")
def root():
    return {"status": "ok"}
