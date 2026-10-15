
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from mnemonic import Mnemonic
from eth_account import Account

# Enable mnemonic-based account creation.
Account.enable_unaudited_hdwallet_features()

CHAINS = {
    "Ethereum": {
        "rpc": "https://ethereum-rpc.publicnode.com",
        "symbol": "ETH",
    },
    "Polygon": {
        "rpc": "https://polygon-bor-rpc.publicnode.com",
        "symbol": "POL",
    },
    "Optimism": {
        "rpc": "https://optimism-rpc.publicnode.com",
        "symbol": "ETH",
    },
    "BNB Smart Chain": {
        "rpc": "https://bsc-rpc.publicnode.com",
        "symbol": "BNB",
    },
    "Arbitrum One": {
        "rpc": "https://arbitrum-one-rpc.publicnode.com",
        "symbol": "ETH",
    },
    "Base": {
        "rpc": "https://mainnet.base.org",
        "symbol": "ETH",
    },
    "Avalanche C-Chain": {
        "rpc": "https://api.avax.network/ext/bc/C/rpc",
        "symbol": "AVAX",
    },
}

LOG_FILE = Path("wallet_test_log.jsonl")
TIMEOUT = 15
PAUSE_SECONDS = 1

mnemo = Mnemonic("english")



def generate_test_wallet():
    """Generate a disposable wallet for testing."""
    phrase = mnemo.generate(strength=128)

    if not mnemo.check(phrase):
        raise RuntimeError("BIP-39 phrase validation failed")

    account = Account.from_mnemonic(phrase)

    return account.address, phrase


def get_native_balance(session, rpc_url, address):
    """Return the native-token balance in whole tokens."""
    response = session.post(
        rpc_url,
        json={
            "jsonrpc": "2.0",
            "method": "eth_getBalance",
            "params": [address, "latest"],
            "id": 1,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    payload = response.json()

    if "error" in payload:
        raise RuntimeError(str(payload["error"]))

    wei = int(payload["result"], 16)
    return wei / 10**18


def check_all_chains(address):
    """Check native-token balances without printing zero balances."""
    results = {}

    with requests.Session() as session:
        for chain_name, config in CHAINS.items():
            try:
                balance = get_native_balance(
                    session,
                    config["rpc"],
                    address,
                )

                results[chain_name] = {
                    "symbol": config["symbol"],
                    "balance": balance,
                    "status": "success",
                }

            except (
                requests.RequestException,
                ValueError,
                RuntimeError,
                KeyError,
            ) as exc:
                results[chain_name] = {
                    "status": "error",
                    "error": str(exc),
                }

    return results

def append_log(record):
    """Append one JSON record to the local log."""
    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")



def run_continuously():
    attempt = 0

    print("Continuous wallet-generation test started.")
    print("Networks:", ", ".join(CHAINS))
    print("Press Ctrl+C to stop.\n")

    while True:
        attempt += 1
        address, phrase = generate_test_wallet()

        # Always print the wallet address.
        print(f"\nAttempt #{attempt}")
        print(f"Address: {address}")

        balances = check_all_chains(address)

        funded_networks = {
            chain_name: data
            for chain_name, data in balances.items()
            if data.get("status") == "success"
            and data.get("balance", 0) > 0
        }

        # Print only networks with a positive balance.
        for chain_name, data in funded_networks.items():
            print(
                f'{chain_name}: {data["balance"]:.8f} '
                f'{data["symbol"]}'
            )

        # Log only if at least one positive balance was found.
        if funded_networks:
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "attempt": attempt,
                "address": address,
                "networks": funded_networks,
                "seed": phrase
            }

            append_log(record)
            print(f"Results appended to {LOG_FILE}")

        time.sleep(PAUSE_SECONDS)

def main():
    try:
        run_continuously()
    except KeyboardInterrupt:
        print("\nTest stopped by user.")
    finally:
        print(f"Log file: {LOG_FILE.resolve()}")


if __name__ == "__main__":
    main()
