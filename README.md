# Canvas calendar sync

Pulls upcoming assignments (and class calendar events, where Canvas has them) from Columbia's Canvas
instance and publishes them as a .ics feed you can subscribe to from Google Calendar, Apple Calendar,
or Outlook. A GitHub Action refreshes the feed every 3 hours.

## Setup (10 minutes)

### 1. Get a Canvas API token

1. Log into courseworks2.columbia.edu.
2. Go to Account > Settings.
3. Scroll to Approved Integrations and click + New Access Token.
4. Purpose: "calendar sync". Leave expiry blank or set something generous.
5. Copy the token immediately - Canvas only shows it once.

### 2. Add repo secrets

Settings > Secrets and variables > Actions > New repository secret.

- CANVAS_BASE_URL = https://courseworks2.columbia.edu
- CANVAS_API_TOKEN = the token from step 1

### 3. Make the repo public

Settings > General > Danger Zone > Change visibility > Public. GitHub Pages on the free plan only
serves public repos. The feed only contains assignment names/dates and course names, no grades, no
personal info.

### 4. Turn on GitHub Pages

Settings > Pages -> Source: Deploy from a branch -> Branch: main, folder: /docs -> Save.

Your feed will be live at:

https://aidandu19.github.io/CANVAS-JOB/canvas.ics

### 5. Run it once manually

Actions tab -> Update Canvas calendar feed -> Run workflow.

### 6. Subscribe from your calendar app

- Google Calendar (desktop): left sidebar -> Other calendars -> + -> From URL -> paste the
  URL above. Google refreshes subscribed feeds roughly every 8-24 hours on its own.
- Apple Calendar: File -> New Calendar Subscription -> paste the same URL.
- Outlook: Add calendar -> Subscribe from web -> paste the same URL.

## What it pulls

- Every assignment with a due date across active courses.
- Calendar events Canvas has recorded for those courses - only includes class sessions if an
  instructor actually put them on the Canvas calendar. Many don't, so "classes" may mostly show
  assignments. That's a Canvas data limitation, not something this script can fix.

## Adjusting the schedule

Edit the cron line in .github/workflows/update-canvas-calendar.yml (UTC). Default is every 3 hours.

## Local test (optional)

pip install requests
export CANVAS_BASE_URL=https://courseworks2.columbia.edu
export CANVAS_API_TOKEN=your_token_here
python scripts/fetch_canvas_ics.py
