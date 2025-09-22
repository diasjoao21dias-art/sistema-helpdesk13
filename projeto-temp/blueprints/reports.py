"""
Blueprint for reports and analytics routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file
from models import Chamado, User, db
from functools import wraps
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
import io
import os

reports_bp = Blueprint('reports', __name__, url_prefix='/relatorios')

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

def reports_access_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_permissions = session.get("permissions", [])
        if "view_reports" not in user_permissions and session.get("role") != "admin":
            flash("Você não tem permissão para acessar relatórios.", "error")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)
    return decorated

@reports_bp.route("/")
@login_required
@reports_access_required
def dashboard():
    # Reports dashboard
    return render_template("relatorios/dashboard.html")

@reports_bp.route("/chamados")
@login_required
@reports_access_required
def tickets_report():
    # Generate tickets report
    return render_template("relatorios/chamados.html")

@reports_bp.route("/usuarios")
@login_required
@reports_access_required
def users_report():
    # Generate users report
    return render_template("relatorios/usuarios.html")

@reports_bp.route("/performance")
@login_required
@reports_access_required
def performance_report():
    # Generate performance report
    return render_template("relatorios/performance.html")

@reports_bp.route("/export/pdf")
@login_required
@reports_access_required
def export_pdf():
    # PDF export logic will be moved here
    pass

@reports_bp.route("/export/excel")
@login_required
@reports_access_required
def export_excel():
    # Excel export logic will be moved here
    pass