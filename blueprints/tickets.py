"""
Blueprint for ticket management routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import Chamado, User, db
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps
import os

tickets_bp = Blueprint('tickets', __name__, url_prefix='/chamados')

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

@tickets_bp.route("/")
@login_required
def list_tickets():
    chamados = Chamado.query.order_by(Chamado.data_abertura.desc()).all()
    return render_template("chamados.html", chamados=chamados)

@tickets_bp.route("/novo", methods=["GET", "POST"])
@login_required
def create_ticket():
    if request.method == "POST":
        # Ticket creation logic will be moved here from app.py
        pass
    return render_template("abrir_chamado.html")

@tickets_bp.route("/editar/<int:ticket_id>", methods=["GET", "POST"])
@login_required
def edit_ticket(ticket_id):
    ticket = Chamado.query.get_or_404(ticket_id)
    
    # Check permissions
    user_permissions = session.get("permissions", [])
    if ("edit_tickets" not in user_permissions and 
        ticket.usuario_id != session.get("user_id") and 
        session.get("role") != "admin"):
        flash("Você não tem permissão para editar este chamado.", "error")
        return redirect(url_for("tickets.list_tickets"))
    
    if request.method == "POST":
        # Ticket editing logic will be moved here
        pass
    
    return render_template("editar_chamado.html", chamado=ticket)

@tickets_bp.route("/fechar/<int:ticket_id>", methods=["GET", "POST"])
@login_required
def close_ticket(ticket_id):
    ticket = Chamado.query.get_or_404(ticket_id)
    
    # Check permissions
    user_permissions = session.get("permissions", [])
    if "close_tickets" not in user_permissions and session.get("role") != "admin":
        flash("Você não tem permissão para fechar chamados.", "error")
        return redirect(url_for("tickets.list_tickets"))
    
    if request.method == "POST":
        # Ticket closing logic will be moved here
        pass
    
    return render_template("fechar_chamado.html", chamado=ticket)

@tickets_bp.route("/view/<int:ticket_id>")
@login_required
def view_ticket(ticket_id):
    ticket = Chamado.query.get_or_404(ticket_id)
    return render_template("view_chamado.html", chamado=ticket)

@tickets_bp.route("/excluir/<int:ticket_id>")
@login_required
def delete_ticket(ticket_id):
    # Check permissions
    user_permissions = session.get("permissions", [])
    if "delete_tickets" not in user_permissions and session.get("role") != "admin":
        flash("Você não tem permissão para excluir chamados.", "error")
        return redirect(url_for("tickets.list_tickets"))
    
    # Ticket deletion logic will be moved here
    return redirect(url_for("tickets.list_tickets"))