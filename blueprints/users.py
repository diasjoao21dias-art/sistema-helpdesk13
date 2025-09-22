"""
Blueprint for user management routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import User, db
from werkzeug.security import generate_password_hash
from functools import wraps
import json

users_bp = Blueprint('users', __name__, url_prefix='/usuarios')

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        
        # Check if user has admin permissions
        user_permissions = session.get("permissions", [])
        if "manage_users" not in user_permissions and session.get("role") != "admin":
            flash("Acesso negado.", "error")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)
    return decorated

@users_bp.route("/")
@admin_required
def list_users():
    users = User.query.all()
    return render_template("admin/usuarios.html", users=users)

@users_bp.route("/novo", methods=["GET", "POST"])
@admin_required
def create_user():
    if request.method == "POST":
        # User creation logic will be moved here
        pass
    return render_template("admin/novo_usuario.html")

@users_bp.route("/editar/<int:user_id>", methods=["GET", "POST"])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        # User editing logic will be moved here
        pass
    return render_template("admin/editar_usuario.html", user=user)

@users_bp.route("/excluir/<int:user_id>")
@admin_required
def delete_user(user_id):
    # User deletion logic will be moved here
    return redirect(url_for("users.list_users"))