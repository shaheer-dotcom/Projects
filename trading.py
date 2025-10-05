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
        print("Connected to Deribit Testnet WebSocket")

    async def authenticate(self):
        """Authenticate with private/auth to get access token."""
       
        auth_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "public/auth",
            "params": {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
        }
        await self.websocket.send(json.dumps(auth_msg))
        response = await self.websocket.recv()
        data = json.loads(response)

        if "result" in data and "access_token" in data["result"]:
            self.token = data["result"]["access_token"]
            print("[+] Authenticated successfully using private/auth")
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
            "amount": amount,
            "instrument_name": instrument_name,
            "type": order_type,
            "label": f"buy_{int(time.time())}"
        }
        if order_type.lower() == "limit":
            params['price'] = price
        print(f"Sending BUY order: {params}")
        result = await self.send_private_request("private/buy", params)
        print("BUY Response:", json.dumps(result, indent=2))
        return result

    async def sell(self, instrument_name, amount, order_type, price=""):
        """Execute a SELL order."""
        params = {
            "amount": amount,
            "instrument_name": instrument_name,
            "type": order_type,
            "label": f"sell_{int(time.time())}"
        }
        if order_type.lower() == "limit":
            params['price'] = price
        print(f"[>] Sending SELL order: {params}")
        result = await self.send_private_request("private/sell", params)
        print("[✓] SELL Response:", json.dumps(result, indent=2))
        return result

    async def get_order_book(self, instrument_name):
        """Fetch public order book."""
        msg = {
            "jsonrpc": "2.0",
            "id": 99,
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
    print("1: GET ORDER BOOK")
    print("2: PLACE BUY ORDER")
    print("3: PLACE SELL ORDER")
    print("Q: EXIT/QUIT")

async def main():
    print("=== Deribit Trading Client ===")
    client_id = input("Enter your Deribit client ID: ")
    client_secret = input("Enter your Deribit client secret: ")

    ##client_id = "piaDhL1a"
    ##client_secret = "J9L0g16X96k_2w4Y6BFzFigq6xNZjcE30JCKyLqzl14"
    trader = DeribitTradingClient(client_id, client_secret)
    await trader.connect()
    await trader.authenticate()
    # -------------
    while True:
        await print_menu()
        choice = input("Enter Your Choice: ")
    
        if (choice == "1"):
            symbol = input("Enter The Symbol: ").upper()
            book = await trader.get_order_book(symbol)
            print(f"\nFetching {symbol} order book...")
            print("Order Book Snapshot:", json.dumps(book, indent=2))
        elif (choice == "2"):
            # print("\nPlacing a test BUY order...")
            symbol = input("Enter The Symbol: ").upper()
            quantity = input("Enter The Amount: ")
            Otype = input("Enter Type Of Order: ")
            if Otype.lower() == "limit":
                price = input("Enter The Price For Symbol: ")
                await trader.buy(symbol,quantity, Otype, price)
            else:  
                await trader.buy(symbol,quantity, Otype)
    
        elif (choice == "3"):
            symbol = input("Enter The Symbol: ").upper()
            quantity = input("Enter The Amount: ")
            Otype = input("Enter Type Of Order: ")
            if Otype.lower() == "limit":
                price = input("Enter The Price For Symbol: ")
                await trader.sell(symbol,quantity, Otype, price)
            else:  
                await trader.buy(symbol,quantity, Otype)
        elif (choice.lower() == "q"):
            await trader.close()
            break
        else:
            print("Invalid Choice")
        time.sleep(3)
        os.system('cls')
    



if __name__ == "__main__":
    asyncio.run(main())