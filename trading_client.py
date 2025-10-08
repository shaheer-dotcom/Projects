import asyncio
import json
import websockets
import time
import os

class DeribitTradingClient:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.url = "wss://test.deribit.com/ws/api/v2"
        self.token = None
        self.websocket = None

    async def connect(self):
        """Connect to Deribit WebSocket."""
        self.websocket = await websockets.connect(self.url)
        print("[+] Connected to Deribit Testnet WebSocket")

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
            print("[+] Authenticated successfully.")
        else:
            print("[-] Authentication failed:", data)
            raise Exception("Authentication error")

    async def send_private_request(self, method, params):
        """Send authenticated (private) API request."""
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
        data = json.loads(response)
        return data

    async def close(self):
        """Close websocket connection."""
        if self.websocket:
            await self.websocket.close()
            print("[x] Connection closed.")

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
    print("=== Deribit Trading Client ===")
    client_id = input("Enter your Deribit client ID: ").strip()
    client_secret = input("Enter your Deribit client secret: ").strip()

    trader = DeribitTradingClient(client_id, client_secret)
    await trader.connect()
    await trader.authenticate()

    while True:
        await print_menu()
        choice = input("Enter Your Choice: ").strip()

        if choice == "1":
            symbol = input("Enter The Symbol (e.g., BTC-PERPETUAL): ").upper()
            book = await trader.get_order_book(symbol)
            print(f"\nOrder Book Snapshot for {symbol}:")
            print(json.dumps(book, indent=2))
            await clear_screen()

        elif choice == "2":
            symbol = input("Enter The Symbol (e.g., BTC-PERPETUAL): ").upper()
            quantity = input("Enter The Amount: ").strip()
            order_type = input("Enter Type Of Order (market/limit): ").strip()
            if order_type.lower() == "limit":
                price = input("Enter The Limit Price: ").strip()
                await trader.buy(symbol, quantity, order_type, price)
            else:
                await trader.buy(symbol, quantity, order_type)
            await clear_screen()

        elif choice == "3":
            symbol = input("Enter The Symbol (e.g., BTC-PERPETUAL): ").upper()
            quantity = input("Enter The Amount: ").strip()
            order_type = input("Enter Type Of Order (market/limit): ").strip()
            if order_type.lower() == "limit":
                price = input("Enter The Limit Price: ").strip()
                await trader.sell(symbol, quantity, order_type, price)
            else:
                await trader.sell(symbol, quantity, order_type)
            await clear_screen()

        elif choice == "4":
            currency = input("Enter Currency (e.g., BTC): ").upper()
            orders = await trader.get_open_limit_orders(currency)

            if not orders:
                print("\n[!] No open limit orders found.")
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
