import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DB_PATH = os.path.join(INSTANCE_DIR, "database.db")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'replace-this-with-a-secure-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + DB_PATH
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# -------- USER MODEL --------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# -------- PROJECT MODEL --------
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    tech_stack = db.Column(db.String(200))
    deployment_url = db.Column(db.String(300))
    visibility = db.Column(db.String(20), default="Private")
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.before_request
def create_db():
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    if not os.path.exists(DB_PATH):
        db.create_all()

# -------- ROUTES --------
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
            flash("Email already registered.", "warning")
            return redirect(url_for("login"))

        user = User(full_name=full_name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("dashboard"))
        flash("Invalid login credentials.", "danger")
        return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    projects = Project.query.filter_by(user_id=current_user.id).all()
    return render_template("dashboard.html", user=current_user, projects=projects)

@app.route("/projects/create", methods=["POST"])
@login_required
def create_project():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    tech_stack = request.form.get("tech_stack", "").strip()
    deployment_url = request.form.get("deployment_url", "").strip()
    visibility = request.form.get("visibility", "Private")

    if not title:
        flash("Project title required.", "danger")
        return redirect(url_for("dashboard"))

    new_project = Project(
        title=title,
        description=description,
        tech_stack=tech_stack,
        deployment_url=deployment_url,
        visibility=visibility,
        user_id=current_user.id
    )
    db.session.add(new_project)
    db.session.commit()
    flash("Project created ✅", "success")
    return redirect(url_for("dashboard"))

@app.route("/projects/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_project(id):
    project = Project.query.get_or_404(id)
    if project.user_id != current_user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        project.title = request.form.get("title")
        project.description = request.form.get("description")
        project.tech_stack = request.form.get("tech_stack")
        project.deployment_url = request.form.get("deployment_url")
        project.visibility = request.form.get("visibility")
        db.session.commit()
        flash("Project updated ✅", "success")
        return redirect(url_for("dashboard"))

    return render_template("edit_project.html", project=project)

@app.route("/projects/<int:id>/delete", methods=["POST"])
@login_required
def delete_project(id):
    project = Project.query.get_or_404(id)
    if project.user_id != current_user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for("dashboard"))
    db.session.delete(project)
    db.session.commit()
    flash("Project deleted ✅", "info")
    return redirect(url_for("dashboard"))

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
