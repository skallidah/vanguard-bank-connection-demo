import json, uuid, openpyxl
from pathlib import Path

DB_FILE = Path(__file__).parent / "data.xlsx"
MOCK_FILE = Path(__file__).parent / "mock-db.json"

SHEETS = ["customers", "vanguardAccounts", "routingDirectory",
          "bankConnectionDrafts", "draftAuthorizations",
          "draftAuthorizationSelections", "bankConnections",
          "bankAuthorizations", "microDeposits"]

def _wb():
    if not DB_FILE.exists():
        _seed()
    return openpyxl.load_workbook(DB_FILE)

def _seed():
    data = json.loads(MOCK_FILE.read_text())
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for sheet in SHEETS:
        rows = data.get(sheet, [])
        ws = wb.create_sheet(sheet)
        if rows:
            ws.append(list(rows[0].keys()))
            for r in rows:
                ws.append([json.dumps(v) if isinstance(v, (list, dict)) else v for v in r.values()])
    wb.save(DB_FILE)

def _sheet_rows(sheet_name):
    wb = _wb()
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = rows[0]
    result = []
    for row in rows[1:]:
        obj = {}
        for h, v in zip(headers, row):
            try:
                obj[h] = json.loads(v) if isinstance(v, str) and v.startswith(('[', '{')) else v
            except Exception:
                obj[h] = v
        result.append(obj)
    return result

def _append_row(sheet_name, record):
    wb = _wb()
    ws = wb[sheet_name]
    headers = [c.value for c in ws[1]]
    ws.append([json.dumps(record.get(h)) if isinstance(record.get(h), (list, dict)) else record.get(h) for h in headers])
    wb.save(DB_FILE)

def _update_row(sheet_name, key_field, key_value, updates):
    wb = _wb()
    ws = wb[sheet_name]
    headers = [c.value for c in ws[1]]
    key_idx = headers.index(key_field)
    for row in ws.iter_rows(min_row=2):
        if row[key_idx].value == key_value:
            for field, val in updates.items():
                col = headers.index(field)
                row[col].value = json.dumps(val) if isinstance(val, (list, dict)) else val
            break
    wb.save(DB_FILE)

# --- Public read helpers ---
def get_routing(routing_number):
    return next((r for r in _sheet_rows("routingDirectory") if r["routingNumber"] == routing_number), None)

def get_draft(draft_id):
    return next((r for r in _sheet_rows("bankConnectionDrafts") if r["draftId"] == draft_id), None)

def get_draft_auth(draft_id):
    return next((r for r in _sheet_rows("draftAuthorizations") if r["draftId"] == draft_id), None)

def get_draft_selection(draft_id):
    return next((r for r in _sheet_rows("draftAuthorizationSelections") if r["draftId"] == draft_id), None)

def get_vanguard_account(va_id):
    return next((r for r in _sheet_rows("vanguardAccounts") if r["vanguardAccountId"] == va_id), None)

def get_customer(customer_id):
    return next((r for r in _sheet_rows("customers") if r["customerId"] == customer_id), None)

# --- Public write helpers ---
def create_draft(record):
    record["draftId"] = "draft_" + uuid.uuid4().hex[:6]
    record["status"] = "DRAFT"
    wb = _wb()
    ws = wb["bankConnectionDrafts"]
    if ws.max_row == 1:
        ws.append(list(record.keys()))
    headers = [c.value for c in ws[1]]
    ws.append([json.dumps(record.get(h)) if isinstance(record.get(h), (list, dict)) else record.get(h) for h in headers])
    wb.save(DB_FILE)
    return record

def update_draft(draft_id, updates):
    _update_row("bankConnectionDrafts", "draftId", draft_id, updates)

def save_draft_selection(draft_id, accounts):
    if not draft_id or accounts is None:
        raise ValueError("draft_id and accounts are required")
    if not isinstance(accounts, list):
        raise TypeError("accounts must be a list")
    rows = _sheet_rows("draftAuthorizationSelections")
    existing = next((r for r in rows if r["draftId"] == draft_id), None)
    if existing:
        _update_row("draftAuthorizationSelections", "draftId", draft_id, {"authorizedVanguardAccounts": accounts})
    else:
        wb = _wb()
        ws = wb["draftAuthorizationSelections"]
        ws.append([draft_id, json.dumps(accounts)])
        wb.save(DB_FILE)

def create_draft_auth(draft_id, draft_owners):
    draft_owner_names = {(o.get('firstName','').lower(), o.get('lastName','').lower()) for o in draft_owners}
    all_vas = _sheet_rows("vanguardAccounts")
    auto, eligible = [], []
    for va in all_vas:
        va_owners = {(o.get('firstName','').lower(), o.get('lastName','').lower()) for o in (va.get('owners') or [])}
        if va_owners and va_owners == draft_owner_names:
            auto.append({"vanguardAccountId": va["vanguardAccountId"], "ownershipMatch": "IDENTICAL"})
        elif va_owners & draft_owner_names:
            eligible.append({"vanguardAccountId": va["vanguardAccountId"], "ownershipMatch": "NON_IDENTICAL"})
    wb = _wb()
    ws = wb["draftAuthorizations"]
    ws.append([draft_id, json.dumps(auto), json.dumps(eligible)])
    wb.save(DB_FILE)

def create_bank_connection(record):
    record["bankConnectionId"] = "bc_" + uuid.uuid4().hex[:6]
    record["status"] = "PENDING_VERIFICATION"
    wb = _wb()
    ws = wb["bankConnections"]
    headers = [c.value for c in ws[1]]
    ws.append([json.dumps(record.get(h)) if isinstance(record.get(h), (list, dict)) else record.get(h) for h in headers])
    wb.save(DB_FILE)
    return record

def create_bank_authorizations(bc_id, va_ids):
    wb = _wb()
    ws = wb["bankAuthorizations"]
    for va_id in va_ids:
        ws.append([bc_id, va_id, "AUTHORIZED"])
    wb.save(DB_FILE)

def create_micro_deposit(bc_id):
    wb = _wb()
    ws = wb["microDeposits"]
    ws.append([bc_id, json.dumps([0.12, 0.07]), "PENDING"])
    wb.save(DB_FILE)
