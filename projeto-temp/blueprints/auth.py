"""
Blueprint for authentication routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from models import User
from activity_logger import log_login, log_logout
import json

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if not username or not password:
            flash("Por favor, preencha todos os campos.", "error")
            return render_template("login.html")
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            session["setor"] = user.setor
            session["permissions"] = json.loads(user.permissions or "[]")
            
            # Log login
            try:
                log_login(user.id, user.username)
            except Exception as e:
                print(f"Erro ao registrar login: {e}")
            
            return redirect(url_for("main.dashboard"))
        else:
            flash("Usuário ou senha inválidos.", "error")
    
    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    try:
        if "user_id" in session and "username" in session:
            log_logout(session["user_id"], session["username"])
    except Exception as e:
        print(f"Erro ao registrar logout: {e}")
    
    session.clear()
    return redirect(url_for("auth.login"))