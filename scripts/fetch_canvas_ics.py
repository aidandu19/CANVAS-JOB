#!/usr/bin/env python3
"""
Pulls upcoming assignments and calendar events from Canvas LMS and writes
an .ics file that any calendar app (Google Calendar, Apple Calendar,
Outlook) can subscribe to by URL.

Requires two environment variables:
  CANVAS_BASE_URL   e.g. https://courseworks2.columbia.edu
  CANVAS_API_TOKEN  a Canvas personal access token (Account > Settings > New Access Token)

Output: docs/canvas.ics (served via GitHub Pages so it has a stable public URL)
"""

import os
import sys
import datetime
import hashlib
import requests

CANVAS_BASE_URL = os.environ.get("CANVAS_BASE_URL", "").rstrip("/")
CANVAS_API_TOKEN = os.environ.get("CANVAS_API_TOKEN", "")

if not CANVAS_BASE_URL or not CANVAS_API_TOKEN:
    print("Missing CANVAS_BASE_URL or CANVAS_API_TOKEN environment variables.", file=sys.stderr)
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {CANVAS_API_TOKEN}"}

LOOKBACK_DAYS = 7
LOOKAHEAD_DAYS = 120

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "canvas.ics")


def paginated_get(url, params=None):
    params = dict(params or {})
    params.setdefault("per_page", 100)
    results = []
    next_url = url
    next_params = params
    while next_url:
        resp = requests.get(next_url, headers=HEADERS, params=next_params, timeout=30)
        resp.raise_for_status()
        results.extend(resp.json())
        next_url = None
        next_params = None
        link = resp.headers.get("Link", "")
        for part in link.split(","):
            part = part.strip()
            if part.endswith('rel="next"'):
                next_url = part[part.index("<") + 1: part.index(">")]
    return results


def get_active_courses():
    url = f"{CANVAS_BASE_URL}/api/v1/courses"
    params = {"enrollment_state": "active", "state[]": "available"}
    return paginated_get(url, params)


def get_assignments(course_id):
    url = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/assignments"
    params = {"order_by": "due_at", "bucket": "future"}
    try:
        return paginated_get(url, params)
    except requests.HTTPError:
        return []


def get_calendar_events(context_codes):
    if not context_codes:
        return []
    now = datetime.datetime.utcnow()
    start = (now - datetime.timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    end = (now + datetime.timedelta(days=LOOKAHEAD_DAYS)).strftime("%Y-%m-%d")
    url = f"{CANVAS_BASE_URL}/api/v1/calendar_events"
    all_events = []
    for i in range(0, len(context_codes), 10):
        chunk = context_codes[i:i + 10]
        params = {
            "type": "event",
            "start_date": start,
            "end_date": end,
            "context_codes[]": chunk,
        }
        try:
            all_events.extend(paginated_get(url, params))
        except requests.HTTPError:
            continue
    return all_events


def escape_ics_text(text):
    if not text:
        return ""
    return (
        text.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def fold_line(line):
    if len(line) <= 75:
        return line
    parts = []
    while len(line) > 75:
        parts.append(line[:75])
        line = " " + line[75:]
    parts.append(line)
    return "\r\n".join(parts)


def to_ics_datetime(dt_str):
    dt = datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%Y%m%dT%H%M%SZ")


def make_uid(seed):
    return hashlib.sha1(seed.encode("utf-8")).hexdigest() + "@canvas-calendar-sync"


def build_ics(assignments_by_course, events, courses_by_id):
    now_stamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//canvas-calendar-sync//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Canvas Assignments & Classes",
        "X-WR-TIMEZONE:UTC",
    ]

    for course_id, assignments in assignments_by_course.items():
        course_name = courses_by_id.get(course_id, f"Course {course_id}")
        for a in assignments:
            due_at = a.get("due_at")
            if not due_at:
                continue
            uid = make_uid(f"assignment-{a['id']}")
            summary = escape_ics_text(f"[{course_name}] {a.get('name', 'Assignment')} due")
            desc = escape_ics_text(a.get("html_url", ""))
            dtstamp = now_stamp
            dtstart = to_ics_datetime(due_at)
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART:{dtstart}",
                f"DTEND:{dtstart}",
                fold_line(f"SUMMARY:{summary}"),
                fold_line(f"DESCRIPTION:{desc}"),
                "END:VEVENT",
            ])

    for e in events:
        start = e.get("start_at")
        end = e.get("end_at") or start
        if not start:
            continue
        uid = make_uid(f"event-{e.get('id')}")
        summary = escape_ics_text(e.get("title", "Class"))
        desc = escape_ics_text(e.get("html_url", ""))
        location = escape_ics_text(e.get("location_name") or "")
        dtstart = to_ics_datetime(start)
        dtend = to_ics_datetime(end)
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            fold_line(f"SUMMARY:{summary}"),
            fold_line(f"DESCRIPTION:{desc}"),
            fold_line(f"LOCATION:{location}"),
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main():
    courses = get_active_courses()
    courses_by_id = {c["id"]: c.get("name", f"Course {c['id']}") for c in courses if "id" in c}
    context_codes = [f"course_{cid}" for cid in courses_by_id]

    assignments_by_course = {}
    for cid in courses_by_id:
        assignments_by_course[cid] = get_assignments(cid)

    events = get_calendar_events(context_codes)

    ics_text = build_ics(assignments_by_course, events, courses_by_id)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="") as f:
        f.write(ics_text)

    total_assignments = sum(len(v) for v in assignments_by_course.values())
    print(f"Wrote {OUTPUT_PATH}: {len(courses_by_id)} courses, "
          f"{total_assignments} assignments, {len(events)} calendar events.")


if __name__ == "__main__":
    main()
