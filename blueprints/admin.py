"""
Blueprint for admin panel routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from models import User, Chamado, db
from functools import wraps
import json
import os
import psutil

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        
        user_permissions = session.get("permissions", [])
        if "admin_access" not in user_permissions and session.get("role") != "admin":
            flash("Acesso negado. Você não é um administrador.", "error")
            return redirect(url_for("main.dashboard"))
        return f(*args, **kwargs)
    return decorated

@admin_bp.route("/")
@admin_required
def dashboard():
    # Admin dashboard statistics
    total_users = User.query.count()
    total_tickets = Chamado.query.count()
    open_tickets = Chamado.query.filter_by(status="Aberto").count()
    
    # System info
    try:
        memory_info = psutil.virtual_memory()
        disk_info = psutil.disk_usage('/')
        system_info = {
            'memory_percent': memory_info.percent,
            'memory_used': round(memory_info.used / (1024**3), 2),
            'memory_total': round(memory_info.total / (1024**3), 2),
            'disk_percent': disk_info.percent,
            'disk_used': round(disk_info.used / (1024**3), 2),
            'disk_total': round(disk_info.total / (1024**3), 2)
        }
    except Exception as e:
        system_info = {'error': str(e)}
    
    stats = {
        'users': total_users,
        'tickets': total_tickets,
        'open_tickets': open_tickets,
        'system': system_info
    }
    
    return render_template("admin/dashboard.html", stats=stats)

@admin_bp.route("/backup")
@admin_required
def backup():
    # Backup functionality will be moved here
    return render_template("admin/backup.html")

@admin_bp.route("/logs")
@admin_required
def logs():
    # Logs viewing functionality will be moved here
    return render_template("admin/logs.html")

@admin_bp.route("/monitoring")
@admin_required
def monitoring():
    # System monitoring will be moved here
    return render_template("admin/monitoring.html")

@admin_bp.route("/monitoring/data")
@admin_required
def monitoring_data():
    # Return JSON data for monitoring dashboard
    try:
        memory_info = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent()
        
        data = {
            'memory_percent': memory_info.percent,
            'cpu_percent': cpu_percent,
            'timestamp': datetime.now().isoformat()
        }
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route("/maintenance", methods=["GET", "POST"])
@admin_required
def maintenance():
    # System maintenance functionality will be moved here
    if request.method == "POST":
        # Handle maintenance actions
        pass
    return render_template("admin/maintenance.html")