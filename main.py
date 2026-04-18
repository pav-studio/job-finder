import os
import json
import random
import smtplib
import requests
import tkinter as tk
from tkinter import messagebox, scrolledtext
from email.message import EmailMessage
from dotenv import load_dotenv

from db import (
    init_db,
    log,
    already_applied,
    save_application,
    count_today_sent
)

load_dotenv()

# =====================================================
# ENV
# =====================================================

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_EMAIL = os.getenv("FROM_EMAIL")

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST")

DAILY_SEND_LIMIT = int(os.getenv("DAILY_SEND_LIMIT", 10))

RESUME_FILE = os.getenv("RESUME_FILE", "resume.pdf")
TEMPLATE_FILE = os.getenv("TEMPLATE_FILE", "mail.json")

PROFILE = {
    "name": os.getenv("FULL_NAME"),
    "phone": os.getenv("PHONE"),
    "email": os.getenv("EMAIL"),
    "location": os.getenv("LOCATION"),
    "github": os.getenv("GITHUB"),
    "linkedin": os.getenv("LINKEDIN")
}

SEARCH_KEYWORDS = [

    # ==================================================
    # INDIA PRIORITY - FULL STACK / FRONTEND
    # ==================================================
    "full stack developer India remote",
    "frontend developer India React remote",
    "SvelteKit developer India remote",
    "Svelte developer India remote",
    "JavaScript developer India remote",
    "Tailwind CSS frontend India remote",
    "React developer India hiring",
    "web developer India startup remote",

    # ==================================================
    # INDIA PRIORITY - BACKEND
    # ==================================================
    "backend engineer India Node.js remote",
    "Node.js developer India remote hiring",
    "Express.js backend India remote",
    "Rust backend engineer India remote",
    "Python backend India remote",
    "Java backend developer India remote",
    "C++ backend engineer India hiring",
    "REST API developer India remote",
    "WebSockets engineer India remote",

    # ==================================================
    # INDIA PRIORITY - DATABASE / GIS
    # ==================================================
    "PostgreSQL developer India remote",
    "PostGIS geospatial engineer India remote",
    "SQLite application developer India",
    "SQL optimization engineer India remote",
    "geolocation backend India remote",

    # ==================================================
    # INDIA PRIORITY - DEVOPS / CLOUD
    # ==================================================
    "AWS cloud engineer India remote",
    "Docker Kubernetes engineer India remote",
    "DevOps engineer India startup remote",
    "CI/CD engineer India remote",
    "Linux systems engineer India remote",

    # ==================================================
    # FLUTTER / CROSS PLATFORM
    # ==================================================
    "Flutter developer India remote",
    "Flutter desktop developer India",
    "Flutter mobile developer India remote",
    "cross platform developer India Flutter",

    # ==================================================
    # REMOTE GLOBAL (OPEN TO INTERNATIONAL)
    # ==================================================
    "remote full stack developer worldwide",
    "remote backend engineer worldwide",
    "remote React developer worldwide",
    "remote Node.js engineer worldwide",
    "remote SvelteKit developer worldwide",
    "remote Flutter developer worldwide",
    "remote Rust engineer worldwide",
    "remote DevOps engineer worldwide",
    "remote software engineer international applicants",
    "remote startup engineer global hiring",

    # ==================================================
    # EXPLICITLY NON-LOCATION RESTRICTED
    # ==================================================
    "remote jobs open worldwide software engineer",
    "remote hiring global candidates developer",
    "remote company hiring international developers",
    "remote engineering jobs work from anywhere",
    "global remote backend engineer hiring",

    # ==================================================
    # STARTUP / FAST GROWTH
    # ==================================================
    "startup full stack developer India remote",
    "startup backend engineer remote worldwide",
    "startup software engineer Node.js India",
    "startup React developer remote global",

    # ==================================================
    # GENERAL FALLBACKS
    # ==================================================
    "software engineer India remote",
    "developer jobs India remote startup",
    "full stack engineer remote hiring",
    "backend developer remote no location restriction"
]

# =====================================================
# HELPERS
# =====================================================

def load_templates():
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def search_jobs():
    print("=" * 70)
    print("[INFO] Starting job search...")

    query = random.choice(SEARCH_KEYWORDS)
    print(f"[INFO] Selected query: {query}")

    url = "https://jsearch.p.rapidapi.com/search"

    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }

    params = {
        "query": query,
        "page": "1",
        "num_pages": "1"
    }

    # ---------------------------------------------
    # ENV CHECKS
    # ---------------------------------------------
    if not RAPIDAPI_KEY:
        print("[ERROR] RAPIDAPI_KEY missing")
        return []

    if not RAPIDAPI_HOST:
        print("[ERROR] RAPIDAPI_HOST missing")
        return []

    print(f"[INFO] URL: {url}")
    print(f"[INFO] HOST: {RAPIDAPI_HOST}")
    print(f"[INFO] PARAMS: {params}")

    # ---------------------------------------------
    # REQUEST
    # ---------------------------------------------
    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=20
        )

        print(f"[INFO] Status Code: {response.status_code}")

    except requests.exceptions.Timeout:
        print("[ERROR] Request timeout")
        return []

    except requests.exceptions.ConnectionError:
        print("[ERROR] Network connection failed")
        return []

    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        return []

    # ---------------------------------------------
    # RAW PREVIEW
    # ---------------------------------------------
    print("-" * 70)
    print("[INFO] Raw response preview:")
    print(response.text[:1000])
    print("-" * 70)

    if response.status_code != 200:
        print(f"[ERROR] Non-200 response: {response.status_code}")
        return []

    # ---------------------------------------------
    # JSON PARSE
    # ---------------------------------------------
    try:
        data = response.json()
        print("[INFO] JSON parsed successfully.")
    except Exception as e:
        print(f"[ERROR] JSON parse failed: {e}")
        return []

    # ---------------------------------------------
    # STRUCTURE DEBUG
    # ---------------------------------------------
    print("[INFO] Top-level JSON keys:")
    print(list(data.keys()))

    raw_jobs = data.get("data") or []

    if not isinstance(raw_jobs, list):
        print("[ERROR] 'data' is not a list")
        print(type(raw_jobs))
        return []

    if len(raw_jobs) == 0:
        print("[WARNING] No jobs returned.")
        return []

    print(f"[INFO] Raw jobs count: {len(raw_jobs)}")

    # ---------------------------------------------
    # PARSE SAFELY
    # ---------------------------------------------
    jobs = []

    for idx, item in enumerate(raw_jobs[:15], start=1):

        if not isinstance(item, dict):
            print(f"[WARNING] Job #{idx} skipped (not dict)")
            continue

        print("=" * 70)
        print(f"[DEBUG] RAW JOB #{idx}")
        print(json.dumps(item, indent=2, ensure_ascii=False)[:3000])

        company = str(item.get("employer_name") or "Unknown").strip()

        role = str(item.get("job_title") or "Software Engineer").strip()

        location = (
            str(item.get("job_city") or "")
            or str(item.get("job_country") or "")
            or "Remote"
        ).strip()

        description = str(item.get("job_description") or "").strip()[:1000]

        website = str(item.get("employer_website") or "").strip()

        apply_link = str(
            item.get("job_apply_link")
            or item.get("job_google_link")
            or ""
        ).strip()

        source = "jsearch"

        # -----------------------------
        # DOMAIN PARSE SAFE
        # -----------------------------
        domain = ""

        if website:
            try:
                domain = (
                    website.replace("https://", "")
                    .replace("http://", "")
                    .replace("www.", "")
                    .split("/")[0]
                    .strip()
                )
            except Exception as e:
                print(f"[WARNING] Domain parse failed: {e}")

        # fallback from apply link
        if not domain and apply_link:
            try:
                domain = (
                    apply_link.replace("https://", "")
                    .replace("http://", "")
                    .replace("www.", "")
                    .split("/")[0]
                    .strip()
                )
            except:
                pass

        email = f"careers@{domain}" if domain else ""

        parsed_job = {
            "company": company,
            "email": email,
            "role": role,
            "location": location,
            "source": source,
            "description": description,
            "website": website,
            "apply_link": apply_link
        }

        print("[PARSED JOB]")
        print(json.dumps(parsed_job, indent=2, ensure_ascii=False))

        jobs.append(parsed_job)

    print("=" * 70)
    print(f"[SUCCESS] Final parsed jobs count: {len(jobs)}")
    print("=" * 70)

    return jobs


def build_email(job):

    templates = load_templates()
    tpl = random.choice(templates)

    subject = tpl["subject"].format(
        company=job["company"],
        role=job["role"],
        name=PROFILE["name"]
    )

    body = tpl["body"].format(
        company=job["company"],
        role=job["role"],
        name=PROFILE["name"],
        email=PROFILE["email"],
        phone=PROFILE["phone"],
        location=PROFILE["location"],
        github=PROFILE["github"],
        linkedin=PROFILE["linkedin"]
    )

    msg = EmailMessage()
    msg["From"] = FROM_EMAIL
    msg["To"] = job["email"]
    msg["Subject"] = subject
    msg.set_content(body)

    if os.path.exists(RESUME_FILE):
        with open(RESUME_FILE, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="pdf",
                filename="Tanishq_Dhote_Resume.pdf"
            )

    return msg


def send_mail(msg):
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)


# =====================================================
# GUI APP
# =====================================================

class JobApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Job Apply Assistant")
        self.root.geometry("900x700")

        self.jobs = []
        self.index = 0

        title = tk.Label(root, text="Job Apply Assistant", font=("Arial", 20, "bold"))
        title.pack(pady=10)

        top_frame = tk.Frame(root)
        top_frame.pack()

        self.search_btn = tk.Button(top_frame, text="Load Jobs", width=20, command=self.load_jobs)
        self.search_btn.grid(row=0, column=0, padx=10)

        self.skip_btn = tk.Button(top_frame, text="Skip", width=20, command=self.skip_job)
        self.skip_btn.grid(row=0, column=1, padx=10)

        self.apply_btn = tk.Button(top_frame, text="Apply", width=20, command=self.apply_job)
        self.apply_btn.grid(row=0, column=2, padx=10)

        self.info = tk.Label(root, text="", font=("Arial", 12))
        self.info.pack(pady=10)

        self.text = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=110, height=30)
        self.text.pack(padx=10, pady=10)

    def load_jobs(self):
        init_db()
        self.jobs = search_jobs()

        filtered = []

        for j in self.jobs:
            if not already_applied(j["company"], j["email"]):
                filtered.append(j)

        self.jobs = filtered
        self.index = 0
        self.show_current()

    def show_current(self):

        if self.index >= len(self.jobs):
            self.info.config(text="No more jobs in stack.")
            self.text.delete("1.0", tk.END)
            return

        job = self.jobs[self.index]

        self.info.config(
            text=f"{self.index+1}/{len(self.jobs)} | {job['company']} | {job['role']} | {job['location']}"
        )

        self.text.delete("1.0", tk.END)

        self.text.insert(tk.END,
            f"Company: {job['company']}\n"
            f"Role: {job['role']}\n"
            f"Location: {job['location']}\n"
            f"Email: {job['email']}\n"
            f"Source: {job['source']}\n\n"
            f"{job['description']}"
        )

    def skip_job(self):
        self.index += 1
        self.show_current()

    def apply_job(self):

        if self.index >= len(self.jobs):
            return

        sent_today = count_today_sent()

        if sent_today >= DAILY_SEND_LIMIT:
            messagebox.showwarning("Limit", "Daily send limit reached.")
            return

        job = self.jobs[self.index]

        try:
            msg = build_email(job)
            send_mail(msg)

            save_application(
                company=job["company"],
                email=job["email"],
                role=job["role"],
                location=job["location"],
                source=job["source"],
                keyword="manual_gui",
                status="sent"
            )

            log("INFO", f"Sent to {job['company']}")

            messagebox.showinfo("Success", f"Applied to {job['company']}")

            self.index += 1
            self.show_current()

        except Exception as e:
            log("ERROR", str(e))
            messagebox.showerror("Failed", str(e))


# =====================================================
# START
# =====================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = JobApp(root)
    root.mainloop()