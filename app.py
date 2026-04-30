from flask import Flask, render_template, request, jsonify, send_from_directory
from core_api import core
from bff_api import bff
import db, os

app = Flask(__name__, static_folder="van_1/assets", static_url_path="/assets")

app.register_blueprint(core)
app.register_blueprint(bff)

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/add-bank")
def add_bank():
    return render_template("add_bank.html")

@app.get("/authorize/<draft_id>")
def authorize(draft_id):
    draft = db.get_draft(draft_id)
    if not draft:
        return "Draft not found", 404
    auth = db.get_draft_auth(draft_id)
    routing = db.get_routing(draft.get("routingNumber", ""))

    def enrich(entry):
        va = db.get_vanguard_account(entry["vanguardAccountId"])
        return {
            "vanguardAccountId": entry["vanguardAccountId"],
            "accountName": va["accountName"] if va else "",
            "managed": va["managed"] if va else False,
            "ownershipMatch": entry.get("ownershipMatch", "NON_IDENTICAL")
        }

    auto = [enrich(e) for e in (auth.get("autoAuthorizedAccounts") or [])] if auth else []
    eligible = [enrich(e) for e in (auth.get("eligibleAdditionalAccounts") or [])] if auth else []
    owners = draft.get("owners") or []
    owner_names = [f"{o.get('firstName','')} {o.get('lastName','')}".strip() for o in owners if isinstance(o, dict)]

    info = {
        "bankName": routing["bankName"] if routing else draft.get("bankName", ""),
        "routingNumber": draft.get("routingNumber"),
        "accountNumber": draft.get("accountNumber"),
        "accountType": draft.get("accountType"),
        "owners": owner_names,
        "correspondentRoutingNumber": routing.get("correspondentRoutingNumber") if routing else None,
        "correspondentAccountNumber": routing.get("correspondentAccountNumber") if routing else None,
    }
    auto_ids = [a["vanguardAccountId"] for a in auto]
    return render_template("authorize.html", draft_id=draft_id, info=info,
                           auto_accounts=auto, eligible_accounts=eligible, auto_ids=auto_ids)

@app.get("/review/<draft_id>")
def review(draft_id):
    draft = db.get_draft(draft_id)
    if not draft:
        return "Draft not found", 404
    selection = db.get_draft_selection(draft_id)
    routing = db.get_routing(draft.get("routingNumber", ""))
    va_ids = (selection.get("authorizedVanguardAccounts") or []) if selection else []
    owners = draft.get("owners") or []
    owner_names = [f"{o.get('firstName','')} {o.get('lastName','')}".strip() for o in owners if isinstance(o, dict)]

    authorized = []
    for va_id in va_ids:
        va = db.get_vanguard_account(va_id)
        if va:
            authorized.append({"vanguardAccountId": va_id, "accountName": va["accountName"], "managed": va["managed"]})

    info = {
        "bankName": routing["bankName"] if routing else draft.get("bankName", ""),
        "routingNumber": draft.get("routingNumber"),
        "accountType": draft.get("accountType"),
        "owners": owner_names,
        "nickname": draft.get("nickname"),
    }
    return render_template("review.html", draft_id=draft_id, info=info,
                           authorized_accounts=authorized,
                           primary_bank=draft.get("makePrimary", False),
                           verification_method="MICRO_DEPOSIT")

@app.get("/success/<bc_id>")
def success(bc_id):
    return render_template("success.html", bc_id=bc_id)

@app.get("/routing-lookup")
def routing_lookup():
    routing_number = request.args.get("routingNumber", "")
    result = db.get_routing(routing_number)
    if result:
        return jsonify({
            "bankName": result["bankName"],
            "correspondentRoutingNumber": result.get("correspondentRoutingNumber"),
            "correspondentAccountNumber": result.get("correspondentAccountNumber")
        })
    return jsonify({"bankName": None}), 404

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=debug, port=port, host="0.0.0.0")
