from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import hashlib
import json
import csv
import io

from database import get_connection, init_db

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key="supersecretkey")

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

init_db()

# ---------------- UTIL ---------------- #

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def log_activity(user_id, action):
    conn = get_connection()
    conn.execute(
        "INSERT INTO logs (user_id, action) VALUES (?, ?)",
        (user_id, action)
    )
    conn.commit()
    conn.close()


# 🔥 Dynamic Age Detection
def detect_age_group(product, niche):
    text = f"{product} {niche}".lower()

    if any(w in text for w in ["baby", "kids", "toys"]):
        return "25-40 (Parents)"
    elif any(w in text for w in ["luxury", "jewelry", "premium", "real estate"]):
        return "28-50 (High income)"
    elif any(w in text for w in ["gaming", "game", "esports"]):
        return "16-30 (Young audience)"
    elif any(w in text for w in ["fitness", "gym", "weight loss"]):
        return "18-35 (Fitness audience)"
    elif any(w in text for w in ["business", "marketing", "coaching"]):
        return "24-45 (Professionals)"
    elif any(w in text for w in ["skincare", "beauty", "cosmetics"]):
        return "18-35 (Beauty audience)"

    return "21-45 (General)"


# 🔥 Audience Generator
def generate_audience(product, niche, location, platform, goal):
    age_group = detect_age_group(product, niche)

    return {
        "demographics": {
            "age_group": age_group,
            "gender": "All",
            "income_level": "Mid to High"
        },
        "psychographics": {
            "interests": [niche, product, "Online Shopping", "Influencers"],
            "values": ["Quality", "Convenience", "Trust"]
        },
        "behavior": {
            "buying_behavior": [
                "Compares options",
                "Reads reviews",
                "Impulse buys during offers"
            ],
            "platform_behavior": f"Active on {platform}",
            "device": "Mobile first users"
        },
        "pain_points": [
            f"Finding reliable {product}",
            "High price confusion"
        ],
        "desires": [
            f"Best {product}",
            "Affordable price"
        ],
        "location": location
    }


# 🔥 Ad Copy Generator
def generate_ad_copy(product, niche, goal):
    return {
        "headlines": [
            f"Best {product} for {niche}",
            f"Upgrade Your {niche} Today",
            f"Top {product} in Market",
            f"Limited Offer on {product}",
            f"Why Everyone Loves This {product}"
        ],
        "primary_texts": [
            f"Struggling with {niche}? Try our {product}",
            f"Discover premium {product}",
            f"Join thousands using {product}",
            f"Stop wasting money, try this",
            f"High quality {product} at best price"
        ],
        "ctas": ["Shop Now", "Learn More", "Try Now"],
        "angles": {
            "emotional": f"Feel confident using {product}",
            "problem_solution": f"Fix your {niche} problems",
            "offer": f"Limited time discount on {product}",
            "social_proof": f"Trusted by thousands"
        }
    }


# ---------------- ROUTES ---------------- #

@app.get("/")
def root():
    return RedirectResponse("/login")


@app.get("/signup")
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})


@app.post("/signup")
def signup(username: str = Form(...), password: str = Form(...)):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hash_password(password))
        )
        conn.commit()
    except Exception as e:
        print("Signup error:", e)
    conn.close()
    return RedirectResponse("/login", status_code=302)


@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = get_connection()

    user = conn.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username, hash_password(password))
    ).fetchone()

    conn.close()

    if user:
        request.session["user"] = {
            "id": user["id"],
            "username": user["username"],
            "is_admin": user["is_admin"]
        }

        log_activity(user["id"], "User Logged In")

        return RedirectResponse("/dashboard", status_code=302)

    return RedirectResponse("/login", status_code=302)


@app.get("/logout")
def logout(request: Request):
    user = request.session.get("user")
    if user:
        log_activity(user["id"], "User Logged Out")

    request.session.clear()
    return RedirectResponse("/login")


@app.get("/dashboard")
def dashboard(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login")

    conn = get_connection()
    ads = conn.execute(
        "SELECT * FROM ads WHERE user_id=?", (user["id"],)
    ).fetchall()
    conn.close()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "ads": ads
    })


@app.post("/generate")
def generate(
    request: Request,
    product: str = Form(...),
    niche: str = Form(...),
    location: str = Form(...),
    platform: str = Form(...),
    goal: str = Form(...)
):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login")

    audience = generate_audience(product, niche, location, platform, goal)
    adcopy = generate_ad_copy(product, niche, goal)

    conn = get_connection()
    conn.execute("""
        INSERT INTO ads (user_id, product, niche, location, platform, goal, audience, adcopy)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user["id"],
        product,
        niche,
        location,
        platform,
        goal,
        json.dumps(audience, indent=2),
        json.dumps(adcopy, indent=2)
    ))
    conn.commit()
    conn.close()

    log_activity(user["id"], f"Generated Ad for {product}")

    return RedirectResponse("/dashboard", status_code=302)


# 🔥 ADMIN DASHBOARD
@app.get("/admin")
def admin(request: Request):
    user = request.session.get("user")

    if not user or user["is_admin"] != 1:
        return RedirectResponse("/login")

    conn = get_connection()
    users = conn.execute("SELECT * FROM users").fetchall()
    ads = conn.execute("SELECT * FROM ads").fetchall()
    logs = conn.execute("SELECT * FROM logs").fetchall()
    conn.close()

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "users": users,
        "ads": ads,
        "logs": logs
    })


# 🔥 CSV DOWNLOAD
@app.get("/download-csv")
def download_csv(request: Request):
    user = request.session.get("user")

    if not user or user["is_admin"] != 1:
        return RedirectResponse("/login")

    conn = get_connection()
    logs = conn.execute("SELECT * FROM logs").fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["User ID", "Action", "Timestamp"])

    for log in logs:
        writer.writerow([log["user_id"], log["action"], log["timestamp"]])

    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=logs.csv"}
    )