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

MAX_APPLICATIONS = int(os.getenv("MAX_APPLICATIONS", 15))

RESUME_FILE = os.getenv("RESUME_FILE", "resume.pdf")
TEMPLATE_FILE = os.getenv("TEMPLATE_FILE", "mail.json")
CONFIG_FILE = os.getenv("CONFIG_FILE", "config.jsonc")

PROFILE = {
    "name": os.getenv("FULL_NAME"),
    "phone": os.getenv("PHONE"),
    "email": os.getenv("EMAIL"),
    "location": os.getenv("LOCATION"),
    "github": os.getenv("GITHUB"),
    "linkedin": os.getenv("LINKEDIN")
}


# =====================================================
# FILE LOGGING (SERVER RESPONSE ONLY)
# =====================================================

def write_server_log(query, response_text):
    try:
        with open("log.txt", "a", encoding="utf-8") as f:
            f.write("=" * 100 + "\n")
            f.write(f"QUERY: {query}\n")
            f.write("-" * 100 + "\n")
            f.write(response_text)
            f.write("\n\n")
    except Exception as e:
        log("ERROR", f"log.txt write failed: {e}")


# =====================================================
# HELPERS
# =====================================================

def load_jsonc(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = []

            for line in f:
                if "//" in line:
                    line = line.split("//")[0]

                lines.append(line)

        data = json.loads("".join(lines))
        return data

    except FileNotFoundError:
        log("ERROR", f"Missing config file: {path}")
        return {
            "skill": [],
            "location": ["Remote"]
        }

    except Exception as e:
        log("ERROR", f"Invalid config file: {e}")
        return {
            "skill": [],
            "location": ["Remote"]
        }


def load_config():
    return load_jsonc(CONFIG_FILE)


def load_templates():
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# =====================================================
# SEO QUERY BUILDER
# =====================================================

def build_query(config):
    skills = config.get("skill", [])
    roles = config.get("role", [])
    locations = config.get("location", [])

    if not skills:
        skills = ["Software"]

    if not roles:
        roles = ["Developer"]

    if not locations:
        locations = ["Remote"]

    skill = random.choice(skills)
    role = random.choice(roles)
    location = random.choice(locations)

    return f"{skill} {role} {location}"


# =====================================================
# SEO SCORE
# =====================================================

def score_job(job, config):
    score = 0

    text = (
        job["role"] + " " +
        job["description"] + " " +
        job["location"]
    ).lower()

    title = job["role"].lower()

    for skill in config.get("skill", []):
        if skill.lower() in text:
            score += 10

    for word in ["remote", "wfh", "work from home", "worldwide"]:
        if word in text:
            score += 15

    for good in ["developer", "engineer"]:
        if good in title:
            score += 8

    for good in ["backend", "frontend", "software", "full stack"]:
        if good in title:
            score += 6

    for bad in ["intern", "sales", "manager", "marketing"]:
        if bad in title:
            score -= 30

    return score


# =====================================================
# SEARCH JOBS
# =====================================================

def search_jobs():
    config = load_config()
    query = build_query(config)

    log("INFO", f"Searching jobs with query: {query}")

    if not RAPIDAPI_KEY:
        log("ERROR", "Missing RAPIDAPI_KEY")
        return []

    if not RAPIDAPI_HOST:
        log("ERROR", "Missing RAPIDAPI_HOST")
        return []

    url = "https://jsearch.p.rapidapi.com/search"

    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }

    params = {
        "query": query,
        "page": "2",
        "num_pages": "5",
        "date_posted": "all",
        "country": config.get("country", "in"),
        "language": config.get("language", "en")
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=20
        )

    except requests.exceptions.Timeout:
        log("ERROR", "API timeout")
        return []

    except requests.exceptions.ConnectionError:
        log("ERROR", "Network connection failed")
        return []

    except Exception as e:
        log("ERROR", f"Request failed: {e}")
        return []

    write_server_log(query, response.text)

    if response.status_code != 200:
        log("ERROR", f"API returned status {response.status_code}")
        return []

    try:
        data = response.json()

    except Exception as e:
        log("ERROR", f"JSON parse failed: {e}")
        return []

    raw_jobs = data.get("data", [])

    if not raw_jobs:
        log("WARNING", "No jobs returned by API")
        return []

    jobs = []

    for item in raw_jobs:
        try:
            company = str(item.get("employer_name") or "Unknown").strip()

            role = str(
                item.get("job_title") or "Software Engineer"
            ).strip()

            location = (
                str(item.get("job_city") or "")
                or str(item.get("job_country") or "")
                or "Remote"
            ).strip()

            description = str(
                item.get("job_description") or ""
            ).strip()[:2500]

            website = str(
                item.get("employer_website") or ""
            ).strip()

            apply_link = str(
                item.get("job_apply_link")
                or item.get("job_google_link")
                or ""
            ).strip()

            src = website or apply_link
            domain = ""

            if src:
                domain = (
                    src.replace("https://", "")
                       .replace("http://", "")
                       .replace("www.", "")
                       .split("/")[0]
                       .strip()
                )

            email = f"careers@{domain}" if domain else ""

            job = {
                "company": company,
                "email": email,
                "role": role,
                "location": location,
                "source": "jsearch",
                "description": description,
                "website": website,
                "apply_link": apply_link
            }

            job["score"] = score_job(job, config)

            jobs.append(job)

        except Exception as e:
            log("WARNING", f"Skipped malformed row: {e}")

    jobs.sort(key=lambda x: x["score"], reverse=True)

    log("INFO", f"Parsed jobs count: {len(jobs)}")

    return jobs


# =====================================================
# EMAIL
# =====================================================

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
                filename="resume.pdf"
            )

    return msg


def send_mail(msg):
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)


# =====================================================
# UI
# =====================================================

class JobApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Job Apply Assistant")
        self.root.geometry("1280x860")

        self.jobs = []
        self.index = 0

        tk.Label(
            root,
            text="JOB APPLY ASSISTANT",
            font=("Consolas", 22, "bold"),
            anchor="w"
        ).pack(fill="x", padx=10, pady=10)

        top = tk.Frame(root)
        top.pack(fill="x", padx=10)

        tk.Button(top, text="Load Jobs", width=18,
                  command=self.load_jobs).pack(side="left", padx=5)

        tk.Button(top, text="Skip", width=18,
                  command=self.skip_job).pack(side="left", padx=5)

        tk.Button(top, text="Apply", width=18,
                  command=self.apply_job).pack(side="left", padx=5)

        self.info = tk.Label(
            root,
            text="No jobs loaded.",
            font=("Consolas", 11),
            justify="left",
            anchor="w"
        )

        self.info.pack(fill="x", padx=10, pady=10)

        self.text = scrolledtext.ScrolledText(
            root,
            wrap=tk.WORD,
            font=("Consolas", 11),
            width=150,
            height=42
        )

        self.text.pack(fill="both", expand=True, padx=10, pady=10)

    def load_jobs(self):
        try:
            init_db()

            self.jobs = search_jobs()

            before = len(self.jobs)

            self.jobs = [
                j for j in self.jobs
                if not already_applied(
                    j["company"],
                    j["email"]
                )
            ]

            removed = before - len(self.jobs)

            if removed:
                log("INFO", f"Filtered duplicates: {removed}")

            if not self.jobs:
                log("WARNING", "No jobs available")
                messagebox.showwarning(
                    "No Jobs",
                    "No jobs found.\nCheck logs."
                )

            self.index = 0
            self.show_current()

        except Exception as e:
            log("ERROR", f"Load jobs failed: {e}")
            messagebox.showerror("Error", str(e))

    def show_current(self):
        if self.index >= len(self.jobs):
            self.info.config(text="No more jobs.")
            self.text.delete("1.0", tk.END)
            return

        job = self.jobs[self.index]

        sent = count_today_sent()

        self.info.config(
            text=(
                f"[{self.index+1}/{len(self.jobs)}]   "
                f"Applied Today: {sent}/{MAX_APPLICATIONS}\n"
                f"Company : {job['company']}\n"
                f"Role    : {job['role']}\n"
                f"Score   : {job['score']}"
            )
        )

        self.text.delete("1.0", tk.END)

        self.text.insert(
            tk.END,
            f"""
==================================================================
COMPANY     : {job['company']}
ROLE        : {job['role']}
LOCATION    : {job['location']}
EMAIL       : {job['email']}
SOURCE      : {job['source']}
SCORE       : {job['score']}
WEBSITE     : {job['website']}
APPLY LINK  : {job['apply_link']}

DESCRIPTION
------------------------------------------------------------------
{job['description']}
==================================================================
"""
        )

    def skip_job(self):
        self.index += 1
        self.show_current()

    def apply_job(self):
        if self.index >= len(self.jobs):
            return

        sent = count_today_sent()

        if sent >= MAX_APPLICATIONS:
            messagebox.showwarning(
                "Limit",
                "Daily application limit reached."
            )
            return

        job = self.jobs[self.index]

        try:
            log("INFO", f"Applying to {job['company']}")

            msg = build_email(job)
            send_mail(msg)

            save_application(
                company=job["company"],
                email=job["email"],
                role=job["role"],
                location=job["location"],
                source=job["source"],
                keyword="seo_search",
                status="sent"
            )

            log("INFO", f"Application sent to {job['company']}")

            messagebox.showinfo(
                "Success",
                f"Applied to {job['company']}"
            )

            self.index += 1
            self.show_current()

        except Exception as e:
            log("ERROR", f"Apply failed: {e}")
            messagebox.showerror("Failed", str(e))


# =====================================================
# START
# =====================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = JobApp(root)
    root.mainloop()