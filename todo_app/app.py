import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, g

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-this-later"  # needed for flash() messages

DATABASE = "todo.db"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    """Open a new database connection if one doesn't already exist for this request."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row  # lets us access columns by name, e.g. row["title"]
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    """Close the database connection at the end of each request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the tasks table if it doesn't already exist. Runs automatically on startup."""
    db = sqlite3.connect(DATABASE)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.commit()
    db.close()


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
    params = []

    if status_filter == "pending":
        sql += " AND status = ?"
        params.append("Pending")
    elif status_filter == "completed":
        sql += " AND status = ?"
        params.append("Completed")

    if query:
        sql += " AND (title LIKE ? OR description LIKE ?)"
        like_term = f"%{query}%"
        params.extend([like_term, like_term])

    sql += " ORDER BY created_at DESC"
    tasks = db.execute(sql, params).fetchall()

    total_tasks = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    pending_count = db.execute(
        "SELECT COUNT(*) FROM tasks WHERE status = 'Pending'"
    ).fetchone()[0]
    completed_count = db.execute(
        "SELECT COUNT(*) FROM tasks WHERE status = 'Completed'"
    ).fetchone()[0]

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

        # Basic form validation
        if not title:
            flash("Task title is required.", "error")
            return render_template(
                "add_task.html", title=title, description=description, due_date=due_date
            )

        db = get_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            """
            INSERT INTO tasks (title, description, due_date, status, created_at, updated_at)
            VALUES (?, ?, ?, 'Pending', ?, ?)
            """,
            (title, description, due_date, now, now),
        )
        db.commit()
        flash("Task added successfully.", "success")
        return redirect(url_for("index"))

    return render_template("add_task.html", title="", description="", due_date="")


@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    """Show the edit-task form (GET) and handle its submission (POST)."""
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

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
            """
            UPDATE tasks
            SET title = ?, description = ?, due_date = ?, updated_at = ?
            WHERE id = ?
            """,
            (title, description, due_date, now, task_id),
        )
        db.commit()
        flash("Task updated successfully.", "success")
        return redirect(url_for("index"))

    return render_template("edit_task.html", task=task)


@app.route("/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    """Delete a task. Confirmation happens client-side in JavaScript before this fires."""
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    if task is None:
        flash("Task not found.", "error")
    else:
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        db.commit()
        flash("Task deleted.", "success")

    return redirect(url_for("index"))


@app.route("/complete/<int:task_id>")
def complete_task(task_id):
    """Mark a task as completed."""
    db = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "UPDATE tasks SET status = 'Completed', updated_at = ? WHERE id = ?",
        (now, task_id),
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
        "UPDATE tasks SET status = 'Pending', updated_at = ? WHERE id = ?",
        (now, task_id),
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
    init_db()  # database + table are created automatically here
    app.run(debug=True)
