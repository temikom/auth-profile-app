import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    current_user,
    UserMixin,
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_FOLDER = os.path.join(BASE_DIR, "instance")
DB_PATH = os.path.join(DB_FOLDER, "database.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET", "replace-this-with-a-secure-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


# ----- Models -----
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    tech_stack = db.Column(db.String(300), nullable=True)  # comma-separated
    feature_checklist = db.Column(db.Text, nullable=True)  # newline-separated
    deployment_url = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(50), default="Active")  # Active / On Hold / Completed
    is_public = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship("User", backref=db.backref("projects", lazy="dynamic"))


# ----- Login loader -----
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ----- DB initialize guard for Flask 3.x -----
@app.before_request
def initialize_database():
    if not os.path.exists(DB_FOLDER):
        os.makedirs(DB_FOLDER, exist_ok=True)
    if not hasattr(app, "db_initialized"):
        db.create_all()
        app.db_initialized = True


# ----- Context processor to use current year in footer -----
@app.context_processor
def inject_current_year():
    return {"current_year": datetime.now().year}


# ----- Routes: Auth & Profile -----
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required.", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("Email already registered. Try logging in.", "warning")
            return redirect(url_for("login"))

        user = User(full_name=full_name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))
        flash("Invalid credentials.", "danger")
        return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    # Pass nothing heavy — template accesses current_user.projects for recent items
    return render_template("dashboard.html")


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.full_name = request.form.get("full_name", "").strip()
        db.session.commit()
        flash("Profile updated!", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html", user=current_user)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("index"))


# ----- Project routes (CRUD) -----
@app.route("/projects")
@login_required
def projects():
    my_projects = Project.query.filter_by(owner_id=current_user.id).order_by(Project.created_at.desc()).all()
    return render_template("projects.html", projects=my_projects)


@app.route("/projects/create", methods=["POST"])
@login_required
def create_project():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    tech_stack = request.form.get("tech_stack", "").strip()
    feature_checklist = request.form.get("feature_checklist", "").strip()
    deployment_url = request.form.get("deployment_url", "").strip()
    status = request.form.get("status", "Active")
    is_public = True if request.form.get("is_public") == "on" else False

    if not title:
        flash("Project title is required.", "danger")
        return redirect(url_for("dashboard"))

    proj = Project(
        owner_id=current_user.id,
        title=title,
        description=description,
        tech_stack=tech_stack,
        feature_checklist=feature_checklist,
        deployment_url=deployment_url,
        status=status,
        is_public=is_public,
    )
    db.session.add(proj)
    db.session.commit()
    flash("Project created.", "success")
    return redirect(url_for("projects"))


@app.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
def edit_project(project_id):
    proj = Project.query.get_or_404(project_id)
    if proj.owner_id != current_user.id:
        abort(403)

    if request.method == "POST":
        proj.title = request.form.get("title", proj.title).strip()
        proj.description = request.form.get("description", proj.description).strip()
        proj.tech_stack = request.form.get("tech_stack", proj.tech_stack).strip()
        proj.feature_checklist = request.form.get("feature_checklist", proj.feature_checklist).strip()
        proj.deployment_url = request.form.get("deployment_url", proj.deployment_url).strip()
        proj.status = request.form.get("status", proj.status)
        proj.is_public = True if request.form.get("is_public") == "on" else False

        db.session.commit()
        flash("Project updated.", "success")
        return redirect(url_for("projects"))

    return render_template("edit_project.html", project=proj)


@app.route("/projects/<int:project_id>/delete", methods=["POST"])
@login_required
def delete_project(project_id):
    proj = Project.query.get_or_404(project_id)
    if proj.owner_id != current_user.id:
        abort(403)
    db.session.delete(proj)
    db.session.commit()
    flash("Project deleted.", "info")
    return redirect(url_for("projects"))


# ----- Run server -----
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
