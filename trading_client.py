""""Deribit Trading Client (Python + MySQL)
A fully asynchronous crypto trading client built with Python, WebSockets, and MySQL.
It connects to the Deribit Testnet API for live authentication, market data retrieval, and trade execution (buy, sell, and cancel orders).
The system also logs all executed trades in a MySQL database with timestamps, allowing users to review their trading history and performance later.

Features:
Connects securely to the Deribit Testnet API via WebSockets
Authenticates using client credentials with trade permissions
Places market and limit buy/sell orders
Cancels specific open limit orders interactively
Fetches live order book data
Stores executed trades in MySQL for record-keeping and analytics
Clean CLI interface with auto screen refresh
Tech Stack: Python (asyncio, websockets, json), MySQL, Deribit API
""""


import asyncio
import json
import websockets
import time
import os
import mysql.connector
from datetime import datetime, timezone


DB_CONFIG = {
    "host": "localhost",
    "user": "root",         
    "password": "",        
    "database": "deribit_trades"
}


class DeribitTradingClient:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.url = "wss://test.deribit.com/ws/api/v2"
        self.token = None
        self.websocket = None
        self.db = self.connect_db()

    def connect_db(self):
        """Connect to MySQL database."""
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            print("Connected to MySQL database successfully.")
            return conn
        except mysql.connector.Error as err:
            print(f"Database connection error: {err}")
            return None

    async def connect(self):
        """Connect to Deribit WebSocket."""
        self.websocket = await websockets.connect(self.url)
        print("Connected to Deribit Testnet WebSocket")

    async def authenticate(self):
        """Authenticate using client credentials."""
        auth_msg = {
            "jsonrpc": "2.0",
            "id": 9929,
            "method": "public/auth",
            "params": {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "trade:read_write"
            }
        }

        await self.websocket.send(json.dumps(auth_msg))
        response = await self.websocket.recv()
        data = json.loads(response)

        if "result" in data and "access_token" in data["result"]:
            self.token = data["result"]["access_token"]
            print("Authenticated successfully.")
        else:
            print("Authentication failed:", data)
            raise Exception("Authentication error")

    async def send_private_request(self, method, params):
        """Send authenticated private API request."""
        if not self.token:
            raise Exception("Client not authenticated. Run authenticate() first.")

        request = {
            "jsonrpc": "2.0",
            "id": int(time.time()),
            "method": method,
            "params": params
        }

        await self.websocket.send(json.dumps(request))
        response = await self.websocket.recv()
        return json.loads(response)

    def save_trade_to_db(self, trade_data):
        """Store trade details in MySQL."""
        if not self.db:
            print("Skipping DB save — not connected to MySQL.")
            return

        try:
            cursor = self.db.cursor()
            sql = """
            INSERT INTO trades (trade_id, side, instrument_name, amount, price, order_type, status, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            values = (
                trade_data.get("order_id", "N/A"),
                trade_data.get("direction", "N/A"),
                trade_data.get("instrument_name", "N/A"),
                trade_data.get("amount", 0),
                trade_data.get("price", 0),
                trade_data.get("order_type", "N/A"),
                trade_data.get("order_state", "N/A"),
               datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

            )
            cursor.execute(sql, values)
            self.db.commit()
            print("Trade saved to database successfully.")
        except mysql.connector.Error as err:
            print(f"Database insert error: {err}")

    async def buy(self, instrument_name, amount, order_type, price=""):
        """Execute a BUY order."""
        params = {
            "amount": float(amount),
            "instrument_name": instrument_name,
            "type": order_type,
            "label": f"buy_{int(time.time())}"
        }
        if order_type.lower() == "limit":
            params["price"] = float(price)

        print(f"Sending BUY order: {params}")
        result = await self.send_private_request("private/buy", params)
        print("BUY Response:", json.dumps(result, indent=2))

        if "result" in result:
            self.save_trade_to_db(result["result"])

        return result

    async def sell(self, instrument_name, amount, order_type, price=""):
        """Execute a SELL order."""
        params = {
            "amount": float(amount),
            "instrument_name": instrument_name,
            "type": order_type,
            "label": f"sell_{int(time.time())}"
        }
        if order_type.lower() == "limit":
            params["price"] = float(price)

        print(f"Sending SELL order: {params}")
        result = await self.send_private_request("private/sell", params)
        print("SELL Response:", json.dumps(result, indent=2))

        if "result" in result:
            self.save_trade_to_db(result["result"])

        return result

    async def get_open_limit_orders(self, currency):
        """Fetch all open LIMIT orders."""
        params = {"currency": currency, "kind": "future"}
        result = await self.send_private_request("private/get_open_orders_by_currency", params)

        if "result" in result:
            orders = [o for o in result["result"] if o["order_type"] == "limit"]
            return orders
        else:
            print("Error fetching open orders:", result)
            return []

    async def cancel_order(self, order_id):
        """Cancel an existing order."""
        print(f"\nCancelling Order ID: {order_id}")
        params = {"order_id": order_id}
        result = await self.send_private_request("private/cancel", params)
        print("Cancel Response:", json.dumps(result, indent=2))
        return result

    async def get_order_book(self, instrument_name):
        """Fetch public order book."""
        msg = {
            "jsonrpc": "2.0",
            "id": 8772,
            "method": "public/get_order_book",
            "params": {"instrument_name": instrument_name}
        }
        await self.websocket.send(json.dumps(msg))
        response = await self.websocket.recv()
        return json.loads(response)

    async def close(self):
        """Close connections."""
        if self.websocket:
            await self.websocket.close()
        if self.db:
            self.db.close()
        print("Connections closed.")

async def print_menu():
    print("\n1: GET ORDER BOOK")
    print("2: PLACE BUY ORDER")
    print("3: PLACE SELL ORDER")
    print("4: CANCEL AN OPEN LIMIT ORDER")
    print("Q: EXIT/QUIT")

async def clear_screen():
    print("\nReturning to menu in 3 seconds...")
    await asyncio.sleep(3)
    os.system("cls" if os.name == "nt" else "clear")

async def main():
    print("Deribit Trading Client")
    client_id = input("Enter your Deribit client ID: ").strip()
    client_secret = input("Enter your Deribit client secret: ").strip()

    trader = DeribitTradingClient(client_id, client_secret)
    await trader.connect()
    await trader.authenticate()

    while True:
        await print_menu()
        choice = input("Enter Your Choice: ").strip()

        if choice == "1":
            symbol = input("Enter Symbol (e.g., BTC-PERPETUAL): ").upper()
            book = await trader.get_order_book(symbol)
            print(json.dumps(book, indent=2))
            await clear_screen()

        elif choice == "2":
            symbol = input("Symbol (e.g., BTC-PERPETUAL): ").upper()
            quantity = input("Amount: ").strip()
            order_type = input("Type (market/limit): ").strip()
            if order_type.lower() == "limit":
                price = input("Limit Price: ").strip()
                await trader.buy(symbol, quantity, order_type, price)
            else:
                await trader.buy(symbol, quantity, order_type)
            await clear_screen()

        elif choice == "3":
            symbol = input("Symbol (e.g., BTC-PERPETUAL): ").upper()
            quantity = input("Amount: ").strip()
            order_type = input("Type (market/limit): ").strip()
            if order_type.lower() == "limit":
                price = input("Limit Price: ").strip()
                await trader.sell(symbol, quantity, order_type, price)
            else:
                await trader.sell(symbol, quantity, order_type)
            await clear_screen()

        elif choice == "4":
            currency = input("Currency (e.g., BTC): ").upper()
            orders = await trader.get_open_limit_orders(currency)
            if not orders:
                print("[!] No open limit orders found.")
                await clear_screen()
                continue

            print("\n=== Open Limit Orders ===")
            for i, order in enumerate(orders, start=1):
                print(f"{i}. ID: {order['order_id']}, Symbol: {order['instrument_name']}, "
                      f"Price: {order['price']}, Amount: {order['amount']}")

            try:
                choice_index = int(input("\nEnter order number to cancel: "))
                if 1 <= choice_index <= len(orders):
                    order_to_cancel = orders[choice_index - 1]["order_id"]
                    await trader.cancel_order(order_to_cancel)
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input.")
            await clear_screen()

        elif choice.lower() == "q":
            await trader.close()
            break
        else:
            print("Invalid choice, try again.")
            await clear_screen()


if __name__ == "__main__":
    asyncio.run(main())

