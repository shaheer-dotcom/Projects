import requests
import datetime
from pymongo import MongoClient
import os

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    # Fallback no-op if python-dotenv is not available
    def load_dotenv(path: str = None):
        return False

# === Load environment variables  ===
# TALOS_API_KEY=your_api_key
# TALOS_API_SECRET=your_secret
# MONGO_URI=mongodb://localhost:27017
load_dotenv()

# === Config ===
API_BASE_URL = "https://api.talos.com" 
API_KEY = os.getenv("TALOS_API_KEY")
API_SECRET = os.getenv("TALOS_API_SECRET")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

# === MongoDB setup ===
client = MongoClient(MONGO_URI)
db = client["talos_trading"]
trades_col = db["trades"]
summaries_col = db["summaries"]

# === Fetch from Talos API ===
def get_trade_summary_from_api(customer_id, currency, exchange_id, date_str):
    """
    Calls Talos endpoint to get order/trade data for a specific customer and date.
    """
    endpoint = f"{API_BASE_URL}/v2/customerOrderSummary" 
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    params = {
        "customerId": customer_id,
        "currency": currency,
        "exchangeId": exchange_id,
        "date": date_str
    }

    response = requests.get(endpoint, headers=headers, params=params)
    if response.status_code != 200:
        raise Exception(f"API error: {response.status_code} {response.text}")

    return response.json()

# === Save trades in MongoDB ===
def store_trades_in_db(customer_id, currency, exchange_id, date_str, data):
    """
    Store each trade record in MongoDB. Avoid duplicates using unique keys.
    """
    trades = data.get("trades", [])
    for trade in trades:
        trade["_customer_id"] = customer_id
        trade["_currency"] = currency
        trade["_exchange_id"] = exchange_id
        trade["_date"] = date_str

    if trades:
        trades_col.insert_many(trades)
        print(f"Stored {len(trades)} trades for {date_str}")
    else:
        print("No trades found for that query")

# === Summarize from MongoDB ===
def summarize_trades_from_db(customer_id, currency, exchange_id, date_str):
    """
    Aggregate trades for a given customer, currency, and exchange.
    """
    pipeline = [
        {"$match": {
            "_customer_id": customer_id,
            "_currency": currency,
            "_exchange_id": exchange_id,
            "_date": date_str,
            "executed": True
        }},
        {"$group": {
            "_id": None,
            "total_trades": {"$sum": 1},
            "total_volume": {"$sum": "$volume"},
            "total_value": {"$sum": "$value"}
        }}
    ]

    result = list(trades_col.aggregate(pipeline))
    if not result:
        return {"total_trades": 0, "total_volume": 0, "total_value": 0}

    summary = result[0]
    return {
        "total_trades": summary["total_trades"],
        "total_volume": summary["total_volume"],
        "total_value": summary["total_value"]
    }

# === Store summary in MongoDB ===
def store_summary(customer_id, currency, exchange_id, date_str, summary):
    """
    Save the computed summary to a separate collection for faster future access.
    """
    record = {
        "customer_id": customer_id,
        "currency": currency,
        "exchange_id": exchange_id,
        "date": date_str,
        "summary": summary,
        "created_at": datetime.datetime.now(datetime.timezone.utc)
    }
    summaries_col.update_one(
        {"customer_id": customer_id, "currency": currency, "exchange_id": exchange_id, "date": date_str},
        {"$set": record},
        upsert=True
    )
    print("[+] Summary stored successfully.")

# === Main CLI ===
def main():
    print("=== Talos Trade Summary ===")
    customer_id = input("Customer ID: ").strip()
    currency = input("Currency (e.g., BTC): ").upper().strip()
    exchange_id = input("Exchange ID: ").strip()
    date_str = input("Date (YYYY-MM-DD): ").strip()

    print("\nFetching trades from Talos API...")
    api_data = get_trade_summary_from_api(customer_id, currency, exchange_id, date_str)

    print("Saving trades in database...")
    store_trades_in_db(customer_id, currency, exchange_id, date_str, api_data)

    print("Generating summary from database...")
    summary = summarize_trades_from_db(customer_id, currency, exchange_id, date_str)

    print("\n=== Trade Summary ===")
    print(f"Customer ID   : {customer_id}")
    print(f"Currency      : {currency}")
    print(f"Exchange ID   : {exchange_id}")
    print(f"Date          : {date_str}")
    print(f"Total Trades  : {summary['total_trades']}")
    print(f"Total Volume  : {summary['total_volume']}")
    print(f"Total Value   : {summary['total_value']}")

    store_summary(customer_id, currency, exchange_id, date_str, summary)

if __name__ == "__main__":
    main()
