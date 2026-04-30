# Vanguard Bank Connection Demo

A local prototype of Vanguard's bank account connection flow. Users enter their bank details, authorize which Vanguard accounts to link, review the summary, and submit — triggering a simulated micro-deposit verification.

## Architecture

The app runs as a single Flask server with three internal layers:

```
Browser → UI Routes (app.py)
             ↓
         BFF API (bff_api.py)   ← orchestrates the user-facing flow
             ↓
         Core API (core_api.py) ← creates bank connections, authorizations, micro-deposits
             ↓
         db.py → data.xlsx      ← Excel file used as the database
```

- **BFF API** (`/bff/...`) manages draft creation, authorization selection, and final submission. On submit it calls the Core API internally via HTTP.
- **Core API** (`/bank-connections/...`) records the bank connection, authorizes Vanguard accounts, and initiates micro-deposits.
- **Database** is an Excel workbook (`data.xlsx`) seeded on first run from `mock-db.json`. Sheets: customers, vanguardAccounts, routingDirectory, bankConnectionDrafts, draftAuthorizations, draftAuthorizationSelections, bankConnections, bankAuthorizations, microDeposits.

## Setup

**Requirements:** Python 3.9+

```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running the App

```bash
python app.py
```

The server starts at `http://localhost:5000`.

On first run, `data.xlsx` is auto-generated from `mock-db.json`. To reset the database to its original state, delete `data.xlsx` and restart.

To enable debug/auto-reload mode:

```bash
FLASK_DEBUG=true python app.py
```

## User Flow

| Step | URL | Description |
|------|-----|-------------|
| 1 | `/` | Landing page explaining the micro-deposit process |
| 2 | `/add-bank` | Enter routing number, account number, account type, and owner info |
| 3 | `/authorize/<draft_id>` | Select which Vanguard accounts to link to this bank |
| 4 | `/review/<draft_id>` | Review all details before submitting |
| 5 | `/success/<bc_id>` | Confirmation page with the new bank connection ID |

## Validating Locally

The mock database includes five pre-seeded drafts. You can jump into any step of the flow directly:

**Authorization step:**
- `http://localhost:5000/authorize/draft_001` — Elizabeth Singleton, Y Bank Test (has auto + eligible accounts)
- `http://localhost:5000/authorize/draft_002` — Michael Turner, JPMorgan Chase (auto-authorized only)

**Review step:**
- `http://localhost:5000/review/draft_001`
- `http://localhost:5000/review/draft_002`

**Full flow from the beginning:**
1. Go to `http://localhost:5000`
2. Click Continue, fill in a routing number from the table below, and submit
3. Follow the authorize → review → submit steps

**Pre-seeded routing numbers:**

| Routing Number | Bank |
|----------------|------|
| `123456789` | Y Bank Test |
| `021000021` | JPMorgan Chase Bank |
| `011000015` | Bank of America |
| `026009593` | Citibank |
| `111000025` | Wells Fargo |

**API endpoints** (for direct testing with curl or Postman):

```bash
# Create a draft
curl -X POST http://localhost:5000/bff/bank-connections/draft \
  -H "Content-Type: application/json" \
  -d '{"routingNumber":"021000021","accountNumber":"12345678","accountType":"CHECKING","owners":[{"firstName":"Michael","lastName":"Turner"}]}'

# Get authorization data for a draft
curl http://localhost:5000/bff/bank-connections/draft/draft_001/authorize

# Submit a draft
curl -X POST http://localhost:5000/bff/bank-connections/draft/draft_001/submit

# Routing number lookup
curl http://localhost:5000/routing-lookup?routingNumber=021000021
```
