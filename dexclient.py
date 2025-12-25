import aiohttp
import asyncio
import time
from heapq import nlargest

# Try broad search keywords to capture many pairs
SEARCH_KEYWORDS = ["eth", "usdt", "sol", "bnb", "btc"]
API_URL = "https://api.dexscreener.com/latest/dex/search"
REFRESH_INTERVAL = 30  # seconds

async def fetch_pairs(session, query):
    """Fetch pairs for a specific keyword."""
    params = {"q": query}
    try:
        async with session.get(API_URL, params=params, timeout=30) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("pairs", [])
            else:
                print(f"[{query}] HTTP error:", resp.status)
    except Exception as e:
        print(f"[{query}] Request failed:", e)
    return []

def top_gainers(all_pairs, n=10, min_liquidity=1000):
    """Return top-N gainers by 24h % change."""
    filtered = []
    for p in all_pairs:
        liq = p.get("liquidity", {}).get("usd", 0)
        chg = p.get("priceChange", {}).get("h24")
        if liq >= min_liquidity and chg is not None:
            filtered.append(p)
    top = nlargest(n, filtered, key=lambda x: x["priceChange"]["h24"])
    return top

async def main():
    async with aiohttp.ClientSession() as session:
        while True:
            all_pairs = []
            for kw in SEARCH_KEYWORDS:
                pairs = await fetch_pairs(session, kw)
                all_pairs.extend(pairs)
                await asyncio.sleep(0.5)  # small delay to be nice to API

            if not all_pairs:
                print("No data received, retrying...")
                await asyncio.sleep(REFRESH_INTERVAL)
                continue

            top = top_gainers(all_pairs)
            print(f"\n=== Top {len(top)} gainers (24h) @ {time.strftime('%X')} ===")
            for i, p in enumerate(top, 1):
                base = p["baseToken"]["symbol"]
                quote = p["quoteToken"]["symbol"]
                change = p["priceChange"]["h24"]
                price = float(p.get("priceUsd") or 0)
                liq = p["liquidity"]["usd"]
                print(f"{i:2}. {base}/{quote:<10} {change:>7.2f}%  ${price:.6f}  liq=${liq:,.0f}")

            await asyncio.sleep(REFRESH_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
