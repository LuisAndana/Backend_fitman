# main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from routers import auth, users, exercises, routines, assignments

app = FastAPI(title="Gym Rutinas API")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(exercises.router)
app.include_router(routines.router)
app.include_router(assignments.router)

# uvicorn main:app --reload
