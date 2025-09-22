"""
Blueprint for main dashboard and core routes
"""
from flask import Blueprint, render_template, session, redirect, url_for, request
from models import User, Chamado, db
from functools import wraps
import json

main_bp = Blueprint('main', __name__)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

@main_bp.route("/")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    
    # Estatísticas básicas
    total_chamados = Chamado.query.count()
    chamados_abertos = Chamado.query.filter_by(status="Aberto").count()
    chamados_fechados = Chamado.query.filter_by(status="Fechado").count()
    
    # Chamados recentes
    chamados_recentes = Chamado.query.order_by(Chamado.data_abertura.desc()).limit(5).all()
    
    stats = {
        'total': total_chamados,
        'abertos': chamados_abertos,
        'fechados': chamados_fechados,
        'em_andamento': total_chamados - chamados_abertos - chamados_fechados
    }
    
    return render_template("dashboard.html", 
                         stats=stats, 
                         chamados=chamados_recentes)

@main_bp.route("/abrir_chamado", methods=["GET", "POST"])
@login_required
def abrir_chamado():
    if request.method == "POST":
        # Logic for creating ticket will be moved here
        pass
    return render_template("abrir_chamado.html")