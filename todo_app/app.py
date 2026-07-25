import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, g
from sqlalchemy import create_engine, text

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-this-later")


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------
# Locally: no DATABASE_URL is set, so we fall back to a SQLite file (todo.db).
# On Render: set a DATABASE_URL env var pointing at their free Postgres
# instance, and this switches automatically -- no code changes needed.
# Render's Postgres URLs start with "postgres://", but SQLAlchemy 1.4+
# requires "postgresql://", so we patch that if present.

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///todo.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)


def get_db():
    """Open a new database connection if one doesn't already exist for this request."""
    if "db" not in g:
        g.db = engine.connect()
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    """Close the database connection at the end of each request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the tasks table if it doesn't already exist. Runs on import, so
    it works both under `python app.py` and under gunicorn."""
    with engine.connect() as db:
        # SERIAL is Postgres syntax for autoincrement; SQLite maps this fine
        # via SQLAlchemy's generic INTEGER PRIMARY KEY handling only if we
        # write dialect-specific DDL, so we branch just for this one line.
        if engine.dialect.name == "postgresql":
            id_column = "id SERIAL PRIMARY KEY"
        else:
            id_column = "id INTEGER PRIMARY KEY AUTOINCREMENT"

        db.execute(text(f"""
            CREATE TABLE IF NOT EXISTS tasks (
                {id_column},
                title TEXT NOT NULL,
                description TEXT,
                due_date TEXT,
                status TEXT NOT NULL DEFAULT 'Pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """))
        db.commit()


init_db()  # runs on import, so gunicorn triggers it too


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Home page: show all tasks, with optional filter and search applied."""
    db = get_db()
    status_filter = request.args.get("filter", "all")  # all | pending | completed
    query = request.args.get("q", "").strip()

    sql = "SELECT * FROM tasks WHERE 1=1"
    params = {}

    if status_filter == "pending":
        sql += " AND status = :status"
        params["status"] = "Pending"
    elif status_filter == "completed":
        sql += " AND status = :status"
        params["status"] = "Completed"

    if query:
        sql += " AND (title LIKE :like_term OR description LIKE :like_term)"
        params["like_term"] = f"%{query}%"

    sql += " ORDER BY created_at DESC"
    tasks = db.execute(text(sql), params).mappings().all()

    total_tasks = db.execute(text("SELECT COUNT(*) FROM tasks")).scalar()
    pending_count = db.execute(
        text("SELECT COUNT(*) FROM tasks WHERE status = 'Pending'")
    ).scalar()
    completed_count = db.execute(
        text("SELECT COUNT(*) FROM tasks WHERE status = 'Completed'")
    ).scalar()

    return render_template(
        "index.html",
        tasks=tasks,
        total_tasks=total_tasks,
        pending_count=pending_count,
        completed_count=completed_count,
        current_filter=status_filter,
        search_query=query,
    )


@app.route("/add", methods=["GET", "POST"])
def add_task():
    """Show the add-task form (GET) and handle its submission (POST)."""
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date = request.form.get("due_date", "").strip()

        if not title:
            flash("Task title is required.", "error")
            return render_template(
                "add_task.html", title=title, description=description, due_date=due_date
            )

        db = get_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            text("""
                INSERT INTO tasks (title, description, due_date, status, created_at, updated_at)
                VALUES (:title, :description, :due_date, 'Pending', :now, :now)
            """),
            {"title": title, "description": description, "due_date": due_date, "now": now},
        )
        db.commit()
        flash("Task added successfully.", "success")
        return redirect(url_for("index"))

    return render_template("add_task.html", title="", description="", due_date="")


@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    """Show the edit-task form (GET) and handle its submission (POST)."""
    db = get_db()
    task = db.execute(
        text("SELECT * FROM tasks WHERE id = :id"), {"id": task_id}
    ).mappings().first()

    if task is None:
        flash("Task not found.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date = request.form.get("due_date", "").strip()

        if not title:
            flash("Task title is required.", "error")
            return render_template("edit_task.html", task=task)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            text("""
                UPDATE tasks
                SET title = :title, description = :description, due_date = :due_date, updated_at = :now
                WHERE id = :id
            """),
            {"title": title, "description": description, "due_date": due_date, "now": now, "id": task_id},
        )
        db.commit()
        flash("Task updated successfully.", "success")
        return redirect(url_for("index"))

    return render_template("edit_task.html", task=task)


@app.route("/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    """Delete a task. Confirmation happens client-side in JavaScript before this fires."""
    db = get_db()
    task = db.execute(
        text("SELECT * FROM tasks WHERE id = :id"), {"id": task_id}
    ).mappings().first()

    if task is None:
        flash("Task not found.", "error")
    else:
        db.execute(text("DELETE FROM tasks WHERE id = :id"), {"id": task_id})
        db.commit()
        flash("Task deleted.", "success")

    return redirect(url_for("index"))


@app.route("/complete/<int:task_id>")
def complete_task(task_id):
    """Mark a task as completed."""
    db = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        text("UPDATE tasks SET status = 'Completed', updated_at = :now WHERE id = :id"),
        {"now": now, "id": task_id},
    )
    db.commit()
    flash("Task marked as completed.", "success")
    return redirect(url_for("index"))


@app.route("/pending/<int:task_id>")
def pending_task(task_id):
    """Mark a completed task back to pending."""
    db = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        text("UPDATE tasks SET status = 'Pending', updated_at = :now WHERE id = :id"),
        {"now": now, "id": task_id},
    )
    db.commit()
    flash("Task marked as pending.", "success")
    return redirect(url_for("index"))


@app.route("/search")
def search():
    """Redirect search-bar submissions to the home page with the query preserved."""
    query = request.args.get("q", "")
    return redirect(url_for("index", q=query))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
