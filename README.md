# Ledger

A client and project tracker I built to learn how real backend systems actually work — not just CRUD, but auth, permissions, and multiple people sharing the same data properly.

**Try it live:** https://ledgerz.onrender.com
**API docs:** https://ledger-api-yae8.onrender.com/docs

(Free hosting means the backend falls asleep after inactivity — if the first request hangs for 30-60 seconds, that's why. Just wait, it'll wake up.)

## What it is

Think of a small consultancy tracking their work: a handful of clients, each with a few projects on the go, each project with its own list of tasks. That's the shape of this app. A client can be shared between teammates — invite someone by username and they get access to everything under that client, not just a read-only view.

I built it as a BBusSc Information Systems student at UCT, mostly to have something on my GitHub that actually does something real, rather than another to-do list tutorial.

## Why it's more than a basic CRUD app

- Real auth — passwords are hashed with bcrypt, sessions are handled with JWT tokens, not a fake login screen
- Clients can have multiple owners/members, not just one fixed creator — this needed an actual many-to-many relationship, not just a single foreign key
- Owner vs. member roles — if the owner leaves, ownership passes to someone else automatically instead of leaving the client orphaned
- PUT and PATCH are both implemented properly and do genuinely different things (full replace vs. partial update)
- Every endpoint returns the right status code — 401 when you're not logged in, 403 when you're logged in but not allowed, 404 when something genuinely doesn't exist
- Has actual tests, not just "I clicked around and it seemed fine"

## Stack

- **Backend:** FastAPI + SQLModel, running on Postgres
- **Auth:** JWT tokens (python-jose), bcrypt password hashing (passlib)
- **Frontend:** plain HTML/CSS/JS, no framework — talks to the API over fetch()
- **Hosted on:** Render (web service + Postgres + static site)
- **Tested with:** pytest

## Running it yourself

```
git clone this-repo
cd ledger-api
python -m venv venv
venv\Scripts\activate      # or source venv/bin/activate on Mac/Linux
pip install -r requirements.txt
```

Create a `.env` file:
```
SECRET_KEY=whatever-random-string-you-want
DATABASE_URL=sqlite:///tasks.db
```

Then:
```
uvicorn main:app --reload
```

Open `static/index.html` in a browser (change `API_BASE` in `static/app.js` to `http://127.0.0.1:8000` first).

Run the tests with:
```
pytest
```

## Things I'd add if I kept going

- Alembic for proper database migrations instead of wiping the database every time the schema changes
- Search and filtering on tasks
- Actual delete confirmations in the UI instead of instant deletes
