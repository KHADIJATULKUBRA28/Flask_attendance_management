from flask import request, jsonify, flash
from flask import Flask, render_template, redirect, url_for, session as flask_session
from functools import wraps
from models import User, Attendance, Task, DailyUpdate
from database import db
from datetime import datetime, date, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'replace-with-a-secure-key'

db.init_app(app)
with app.app_context():
    db.create_all()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def login_required(f):
    """Decorator to protect routes that need authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in flask_session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Return the current logged-in User or None."""
    user_id = flask_session.get('user_id')
    if user_id:
        return db.session.get(User, user_id)
    return None


@app.context_processor
def inject_globals():
    user = get_current_user()
    return {'user': user, 'today': date.today()}


# ─── Public Pages ─────────────────────────────────────────────────────────────

@app.route("/")
def home():
    if 'user_id' in flask_session:
        return redirect(url_for('dashboard'))
    return render_template("home.html")


@app.route("/about")
def about():
    return render_template("about.html")


# ─── Auth ─────────────────────────────────────────────────────────────────────

@app.route("/signup", methods=["POST", "GET"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("signup.html")

        if User.query.filter_by(email=email).first():
            flash("Email already exists.", "danger")
            return render_template("signup.html")

        if User.query.filter_by(name=name).first():
            flash("Name already taken.", "danger")
            return render_template("signup.html")

        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Account created! Please log in.", "success")
        return redirect(url_for('login'))
    return render_template("signup.html")


@app.route("/login", methods=["POST", "GET"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            flask_session['user_id'] = user.id
            flash(f"Welcome back, {user.name}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid email or password.", "danger")
            return render_template("login.html")
    return render_template("login.html")


@app.route("/logout")
def logout():
    flask_session.pop('user_id', None)
    flash("You've been logged out.", "info")
    return redirect(url_for('home'))


# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    today = date.today()

    # Today's attendance
    today_attendance = Attendance.query.filter_by(user_id=user.id, date=today).first()

    # Task stats
    total_tasks = Task.query.filter_by(user_id=user.id).count()
    todo_tasks = Task.query.filter_by(user_id=user.id, status='todo').count()
    in_progress_tasks = Task.query.filter_by(user_id=user.id, status='in_progress').count()
    done_tasks = Task.query.filter_by(user_id=user.id, status='done').count()

    # Overall progress
    all_tasks = Task.query.filter_by(user_id=user.id).all()
    overall_progress = 0
    if all_tasks:
        overall_progress = round(sum(t.progress for t in all_tasks) / len(all_tasks))

    # Recent tasks
    recent_tasks = Task.query.filter_by(user_id=user.id).order_by(Task.updated_at.desc()).limit(5).all()

    # Attendance streak
    streak = 0
    check_date = today
    while True:
        att = Attendance.query.filter_by(user_id=user.id, date=check_date).first()
        if att and att.check_in:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    # Recent updates
    recent_updates = DailyUpdate.query.filter_by(user_id=user.id).order_by(DailyUpdate.created_at.desc()).limit(5).all()

    return render_template("dashboard.html",
                           today_attendance=today_attendance,
                           total_tasks=total_tasks,
                           todo_tasks=todo_tasks,
                           in_progress_tasks=in_progress_tasks,
                           done_tasks=done_tasks,
                           overall_progress=overall_progress,
                           recent_tasks=recent_tasks,
                           streak=streak,
                           recent_updates=recent_updates)


# ─── Attendance ───────────────────────────────────────────────────────────────

@app.route("/attendance")
@login_required
def attendance():
    user = get_current_user()
    records = Attendance.query.filter_by(user_id=user.id).order_by(Attendance.date.desc()).all()
    today = date.today()
    today_record = Attendance.query.filter_by(user_id=user.id, date=today).first()

    # Monthly stats
    first_of_month = today.replace(day=1)
    month_records = Attendance.query.filter(
        Attendance.user_id == user.id,
        Attendance.date >= first_of_month,
        Attendance.date <= today
    ).all()
    days_present = sum(1 for r in month_records if r.check_in)
    days_in_month = today.day
    attendance_rate = round((days_present / days_in_month) * 100) if days_in_month else 0

    # Build calendar data for current month (for heatmap)
    calendar_data = {}
    for r in month_records:
        calendar_data[r.date.isoformat()] = {
            'status': r.status,
            'check_in': r.check_in.strftime('%H:%M') if r.check_in else None,
            'check_out': r.check_out.strftime('%H:%M') if r.check_out else None,
        }

    return render_template("attendance.html",
                           records=records,
                           today_record=today_record,
                           days_present=days_present,
                           days_in_month=days_in_month,
                           attendance_rate=attendance_rate,
                           calendar_data=calendar_data,
                           today=today)


@app.route("/attendance/checkin", methods=["POST"])
@login_required
def checkin():
    user = get_current_user()
    today = date.today()
    record = Attendance.query.filter_by(user_id=user.id, date=today).first()

    if record and record.check_in:
        flash("You've already checked in today!", "warning")
    else:
        now = datetime.now()
        if not record:
            record = Attendance(user_id=user.id, date=today, check_in=now, status='present')
            db.session.add(record)
        else:
            record.check_in = now
        # Mark as late if after 9:30 AM
        if now.hour > 9 or (now.hour == 9 and now.minute > 30):
            record.status = 'late'
        db.session.commit()
        flash(f"Checked in at {now.strftime('%I:%M %p')}!", "success")

    return redirect(request.referrer or url_for('dashboard'))


@app.route("/attendance/checkout", methods=["POST"])
@login_required
def checkout():
    user = get_current_user()
    today = date.today()
    record = Attendance.query.filter_by(user_id=user.id, date=today).first()

    if not record or not record.check_in:
        flash("You haven't checked in today!", "warning")
    elif record.check_out:
        flash("You've already checked out today!", "warning")
    else:
        record.check_out = datetime.now()
        db.session.commit()
        flash(f"Checked out at {record.check_out.strftime('%I:%M %p')}!", "success")

    return redirect(request.referrer or url_for('dashboard'))


# ─── Tasks ────────────────────────────────────────────────────────────────────

@app.route("/tasks")
@login_required
def tasks():
    user = get_current_user()
    status_filter = request.args.get('status', 'all')
    priority_filter = request.args.get('priority', 'all')

    query = Task.query.filter_by(user_id=user.id)
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    if priority_filter != 'all':
        query = query.filter_by(priority=priority_filter)

    all_tasks = query.order_by(Task.created_at.desc()).all()

    # Stats for filter badges
    stats = {
        'all': Task.query.filter_by(user_id=user.id).count(),
        'todo': Task.query.filter_by(user_id=user.id, status='todo').count(),
        'in_progress': Task.query.filter_by(user_id=user.id, status='in_progress').count(),
        'done': Task.query.filter_by(user_id=user.id, status='done').count(),
    }

    return render_template("tasks.html",
                           tasks=all_tasks,
                           stats=stats,
                           current_status=status_filter,
                           current_priority=priority_filter)


@app.route("/tasks/new", methods=["GET", "POST"])
@login_required
def new_task():
    user = get_current_user()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        priority = request.form.get("priority", "medium")
        due_date_str = request.form.get("due_date", "")

        if not title:
            flash("Task title is required.", "danger")
            return render_template("task_form.html", editing=False)

        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except ValueError:
                flash("Invalid date format.", "danger")
                return render_template("task_form.html", editing=False)

        task = Task(user_id=user.id, title=title, description=description,
                    priority=priority, due_date=due_date)
        db.session.add(task)
        db.session.commit()
        flash("Task created successfully!", "success")
        return redirect(url_for('tasks'))

    return render_template("task_form.html", editing=False)


@app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    user = get_current_user()
    task = Task.query.filter_by(id=task_id, user_id=user.id).first_or_404()

    if request.method == "POST":
        task.title = request.form.get("title", "").strip()
        task.description = request.form.get("description", "").strip()
        task.priority = request.form.get("priority", "medium")
        task.status = request.form.get("status", task.status)
        progress_val = request.form.get("progress", "0")
        try:
            task.progress = max(0, min(100, int(progress_val)))
        except ValueError:
            task.progress = 0

        due_date_str = request.form.get("due_date", "")
        if due_date_str:
            try:
                task.due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        # Auto-set progress/status consistency
        if task.status == 'done':
            task.progress = 100
        elif task.progress == 100:
            task.status = 'done'
        elif task.progress > 0 and task.status == 'todo':
            task.status = 'in_progress'

        task.updated_at = datetime.utcnow()
        db.session.commit()
        flash("Task updated!", "success")
        return redirect(url_for('tasks'))

    return render_template("task_form.html", editing=True, task=task)


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    user = get_current_user()
    task = Task.query.filter_by(id=task_id, user_id=user.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "info")
    return redirect(url_for('tasks'))


@app.route("/tasks/<int:task_id>/update-status", methods=["POST"])
@login_required
def update_task_status(task_id):
    user = get_current_user()
    task = Task.query.filter_by(id=task_id, user_id=user.id).first_or_404()
    new_status = request.form.get("status", task.status)

    if new_status in ('todo', 'in_progress', 'done'):
        task.status = new_status
        if new_status == 'done':
            task.progress = 100
        elif new_status == 'todo':
            task.progress = 0
        task.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f"Task marked as {new_status.replace('_', ' ')}.", "success")

    return redirect(request.referrer or url_for('tasks'))


@app.route("/tasks/<int:task_id>/update-progress", methods=["POST"])
@login_required
def update_task_progress(task_id):
    user = get_current_user()
    task = Task.query.filter_by(id=task_id, user_id=user.id).first_or_404()
    progress_val = request.form.get("progress", "0")
    try:
        task.progress = max(0, min(100, int(progress_val)))
    except ValueError:
        task.progress = 0

    if task.progress == 100:
        task.status = 'done'
    elif task.progress > 0 and task.status == 'todo':
        task.status = 'in_progress'

    task.updated_at = datetime.utcnow()
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(success=True, progress=task.progress, status=task.status)

    flash("Progress updated!", "success")
    return redirect(request.referrer or url_for('tasks'))


# ─── Daily Updates ────────────────────────────────────────────────────────────

@app.route("/daily-updates")
@login_required
def daily_updates():
    user = get_current_user()
    updates = DailyUpdate.query.filter_by(user_id=user.id).order_by(DailyUpdate.date.desc(), DailyUpdate.created_at.desc()).all()
    user_tasks = Task.query.filter_by(user_id=user.id).filter(Task.status != 'done').order_by(Task.title).all()

    # Group updates by date
    grouped = {}
    for u in updates:
        key = u.date.isoformat()
        if key not in grouped:
            grouped[key] = {'date': u.date, 'updates': []}
        grouped[key]['updates'].append(u)

    total_hours = sum(u.hours_spent for u in updates)
    return render_template("daily_updates.html",
                           grouped_updates=grouped,
                           user_tasks=user_tasks,
                           total_hours=total_hours)


@app.route("/daily-updates/new", methods=["POST"])
@login_required
def new_daily_update():
    user = get_current_user()
    content = request.form.get("content", "").strip()
    task_id = request.form.get("task_id", "")
    hours_str = request.form.get("hours_spent", "0")

    if not content:
        flash("Update content is required.", "danger")
        return redirect(url_for('daily_updates'))

    try:
        hours = max(0.0, float(hours_str))
    except ValueError:
        hours = 0.0

    update = DailyUpdate(
        user_id=user.id,
        task_id=int(task_id) if task_id else None,
        date=date.today(),
        content=content,
        hours_spent=hours
    )
    db.session.add(update)
    db.session.commit()
    flash("Daily update logged!", "success")
    return redirect(url_for('daily_updates'))


@app.route("/daily-updates/<int:update_id>/delete", methods=["POST"])
@login_required
def delete_daily_update(update_id):
    user = get_current_user()
    update = DailyUpdate.query.filter_by(id=update_id, user_id=user.id).first_or_404()
    db.session.delete(update)
    db.session.commit()
    flash("Update deleted.", "info")
    return redirect(url_for('daily_updates'))


# ─── API (Dashboard Charts) ──────────────────────────────────────────────────

@app.route("/api/dashboard-stats")
@login_required
def dashboard_stats():
    user = get_current_user()
    today = date.today()

    # Weekly activity: tasks completed per day for last 7 days
    weekly = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        count = DailyUpdate.query.filter_by(user_id=user.id, date=d).count()
        weekly.append({'date': d.strftime('%a'), 'count': count})

    # Task distribution
    todo = Task.query.filter_by(user_id=user.id, status='todo').count()
    in_progress = Task.query.filter_by(user_id=user.id, status='in_progress').count()
    done = Task.query.filter_by(user_id=user.id, status='done').count()

    return jsonify({
        'weekly': weekly,
        'task_distribution': {'todo': todo, 'in_progress': in_progress, 'done': done}
    })


# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)