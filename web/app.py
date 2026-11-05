"""Flask entry point for the Project 7 website and API."""

from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

app = Flask(__name__)
app.json.ensure_ascii = False


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return {"status": "ok"}
