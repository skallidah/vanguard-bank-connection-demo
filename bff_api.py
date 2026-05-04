from flask import Blueprint, request, jsonify
from urllib.parse import urlparse
import db, os, requests as http

bff = Blueprint("bff", __name__)
CORE = f"http://localhost:{os.environ.get('PORT', 5000)}"

_CORE_HOST = urlparse(CORE).netloc

def _safe_core_url(path):
    parsed = urlparse(f"{CORE}{path}")
    if parsed.netloc != _CORE_HOST:
        raise ValueError(f"Blocked request to untrusted host: {parsed.netloc}")
    return parsed.geturl()

def _owner_names(owners):
    if isinstance(owners, list):
        return [f"{o.get('firstName','')} {o.get('lastName','')}".strip() for o in owners]
    return []

# POST /bff/bank-connections/draft
@bff.post("/bff/bank-connections/draft")
def create_draft():
    body = request.json
    routing = db.get_routing(body.get("routingNumber", ""))
    record = {
        "customerId": body.get("customerId", "cust_10001"),
        "routingNumber": body.get("routingNumber"),
        "accountNumber": body.get("accountNumber"),
        "accountType": body.get("accountType"),
        "owners": body.get("owners", []),
        "nickname": body.get("nickname"),
        "makePrimary": body.get("makePrimary", False),
        "correspondentRoutingNumber": body.get("correspondentRoutingNumber"),
        "correspondentAccountNumber": body.get("correspondentAccountNumber"),
        "bankName": routing["bankName"] if routing else "Unknown",
    }
    draft = db.create_draft(record)
    db.create_draft_auth(draft["draftId"], body.get("owners", []))
    return jsonify({"draftId": draft["draftId"], "status": "DRAFT"}), 201

# PUT /bff/bank-connections/draft/<draftId>
@bff.put("/bff/bank-connections/draft/<draft_id>")
def update_draft(draft_id):
    body = request.json
    routing = db.get_routing(body.get("routingNumber", ""))
    updates = {k: v for k, v in body.items()}
    if routing:
        updates["bankName"] = routing["bankName"]
    db.update_draft(draft_id, updates)
    return jsonify({"draftId": draft_id, "status": "DRAFT"}), 200

# GET /bff/bank-connections/draft/<draftId>/authorize
@bff.get("/bff/bank-connections/draft/<draft_id>/authorize")
def get_authorize(draft_id):
    draft = db.get_draft(draft_id)
    if not draft:
        return jsonify({"error": "Draft not found"}), 404

    auth = db.get_draft_auth(draft_id)
    routing = db.get_routing(draft.get("routingNumber", ""))

    def enrich(entry):
        va = db.get_demo_account(entry["demoAccountId"])
        return {
            "demoAccountId": entry["demoAccountId"],
            "accountName": va["accountName"] if va else "",
            "managed": va["managed"] if va else False,
            "ownershipMatch": entry.get("ownershipMatch", "NON_IDENTICAL")
        }

    auto = [enrich(e) for e in (auth.get("autoAuthorizedAccounts") or [])] if auth else []
    eligible = [enrich(e) for e in (auth.get("eligibleAdditionalAccounts") or [])] if auth else []

    return jsonify({
        "bankInformation": {
            "bankName": routing["bankName"] if routing else draft.get("bankName", ""),
            "routingNumber": draft.get("routingNumber"),
            "accountNumber": draft.get("accountNumber"),
            "accountType": draft.get("accountType"),
            "owners": _owner_names(draft.get("owners") or []),
            "correspondentRoutingNumber": routing.get("correspondentRoutingNumber") if routing else None,
            "correspondentAccountNumber": routing.get("correspondentAccountNumber") if routing else None,
        },
        "autoAuthorizedAccounts": auto,
        "eligibleAdditionalAccounts": eligible
    }), 200

# POST /bff/bank-connections/draft/<draftId>/authorizations
@bff.post("/bff/bank-connections/draft/<draft_id>/authorizations")
def save_authorizations(draft_id):
    body = request.json
    accounts = body.get("authorizedAccounts", [])
    db.save_draft_selection(draft_id, accounts)
    return jsonify({"draftId": draft_id, "authorizedAccounts": accounts}), 200

# GET /bff/bank-connections/draft/<draftId>/review
@bff.get("/bff/bank-connections/draft/<draft_id>/review")
def get_review(draft_id):
    draft = db.get_draft(draft_id)
    if not draft:
        return jsonify({"error": "Draft not found"}), 404

    selection = db.get_draft_selection(draft_id)
    routing = db.get_routing(draft.get("routingNumber", ""))
    va_ids = selection.get("authorizedAccounts") or [] if selection else []

    authorized = []
    for va_id in va_ids:
        va = db.get_demo_account(va_id)
        if va:
            authorized.append({
                "demoAccountId": va_id,
                "accountName": va["accountName"],
                "managed": va["managed"]
            })

    return jsonify({
        "bankInformation": {
            "bankName": routing["bankName"] if routing else draft.get("bankName", ""),
            "routingNumber": draft.get("routingNumber"),
            "accountType": draft.get("accountType"),
            "owners": _owner_names(draft.get("owners") or []),
            "nickname": draft.get("nickname"),
        },
        "authorizedAccounts": authorized,
        "primaryBank": draft.get("makePrimary", False),
        "verificationMethod": "MICRO_DEPOSIT"
    }), 200

# POST /bff/bank-connections/draft/<draftId>/submit
@bff.post("/bff/bank-connections/draft/<draft_id>/submit")
def submit_draft(draft_id):
    draft = db.get_draft(draft_id)
    if not draft:
        return jsonify({"error": "Draft not found"}), 404

    selection = db.get_draft_selection(draft_id)
    va_ids = selection.get("authorizedAccounts") or [] if selection else []

    # 1. Create bank connection (core)
    conn_payload = {
        "customerId": draft.get("customerId"),
        "routingNumber": draft.get("routingNumber"),
        "accountNumberToken": draft.get("accountNumber", ""),
        "accountType": draft.get("accountType"),
        "owners": draft.get("owners") or [],
        "nickname": draft.get("nickname"),
        "primary": draft.get("makePrimary", False),
    }
    conn_resp = http.post(_safe_core_url("/bank-connections"), json=conn_payload)
    conn = conn_resp.json()
    bc_id = conn["bankConnectionId"]

    # 2. Create authorizations (core)
    http.post(_safe_core_url(f"/bank-connections/{bc_id}/authorizations"),
              json={"accountIds": va_ids})

    # 3. Initiate micro-deposits (core)
    http.post(_safe_core_url(f"/bank-connections/{bc_id}/micro-deposits"))

    # 4. Mark draft submitted
    db.update_draft(draft_id, {"status": "SUBMITTED"})

    return jsonify({"bankConnectionId": bc_id, "status": "PENDING_VERIFICATION"}), 201
