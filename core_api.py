from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
import db

core = Blueprint("core", __name__)

@core.post("/bank-connections")
def create_bank_connection():
    body = request.json
    routing = db.get_routing(body.get("routingNumber", ""))
    record = {
        "customerId": body.get("customerId"),
        "routingNumber": body.get("routingNumber"),
        "bankName": routing["bankName"] if routing else "Unknown",
        "accountNumberToken": "tok_" + body.get("accountNumberToken", "")[:6],
        "accountType": body.get("accountType"),
        "owners": body.get("owners", []),
        "nickname": body.get("nickname"),
        "primary": body.get("primary", False),
    }
    conn = db.create_bank_connection(record)
    return jsonify({
        "bankConnectionId": conn["bankConnectionId"],
        "status": conn["status"],
        "createdAt": datetime.now(timezone.utc).isoformat()
    }), 201

@core.post("/bank-connections/<bc_id>/authorizations")
def create_authorizations(bc_id):
    body = request.json
    va_ids = body.get("accountIds", [])
    db.create_bank_authorizations(bc_id, va_ids)
    return jsonify({"bankConnectionId": bc_id, "authorizedAccounts": va_ids}), 200

@core.post("/bank-connections/<bc_id>/micro-deposits")
def initiate_micro_deposits(bc_id):
    db.create_micro_deposit(bc_id)
    return jsonify({"bankConnectionId": bc_id, "status": "INITIATED"}), 202
