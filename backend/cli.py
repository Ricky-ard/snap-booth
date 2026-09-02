"""Local CLI: reset admin password when there is no email recovery.

Usage:
    python cli.py reset-password NEW_PASSWORD [--pin 1234]
"""
import asyncio, sys, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")
from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt


async def _run(pw: str, pin: str | None):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    doc = {"password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()}
    if pin:
        doc["pin"] = pin
    await db.settings.update_one({"_id": "admin"}, {"$set": doc}, upsert=True)
    print("admin password reset.")
    client.close()


def main():
    args = sys.argv[1:]
    if not args or args[0] != "reset-password":
        print("usage: python cli.py reset-password NEW_PASSWORD [--pin 1234]")
        sys.exit(1)
    if len(args) < 2:
        print("missing password")
        sys.exit(1)
    pw = args[1]
    pin = None
    if "--pin" in args:
        pin = args[args.index("--pin") + 1]
    asyncio.run(_run(pw, pin))


if __name__ == "__main__":
    main()
