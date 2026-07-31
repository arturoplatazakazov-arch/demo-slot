#!/usr/bin/env python3
"""Bring the local dev Postgres up, healthy, and bootstrapped.

Called by dev.sh / start.command. Prints the server URI on stdout; every
diagnostic goes to stderr so the caller can capture just the URI.

Robust against the recurring failure where macOS purges /private/tmp and
deletes files out from under the running cluster (`global/pg_filenode.map`
goes missing, new connections die): if the server can't answer a real query,
it's torn down and reinitialised from scratch. The dev DB is disposable — the
app reseeds every game on its next startup.
"""
import shutil
import subprocess
import sys
import time

import pgserver
import psycopg

DEFAULT_PGDATA = "/private/tmp/demo_slot_pgdata"


def ensure_ready(pgdata: str):
    """Start (or attach to) the cluster and confirm a query round-trips.

    pg_ctl's -w only waits for the postmaster to accept a connection, not for
    it to actually serve queries — so we probe with a real SELECT before
    declaring it ready, and treat any failure as "not ready yet".
    """
    srv = pgserver.get_server(pgdata, cleanup_mode=None)
    last_err = None
    for _ in range(30):
        try:
            with psycopg.connect(srv.get_uri(), connect_timeout=1) as conn:
                conn.execute("SELECT 1")
            return srv
        except Exception as exc:  # noqa: BLE001 — any connect/query failure = not ready
            last_err = exc
            time.sleep(0.5)
    raise RuntimeError(f"Postgres did not become ready: {last_err}")


def main() -> None:
    pgdata = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PGDATA

    try:
        srv = ensure_ready(pgdata)
    except Exception as exc:  # noqa: BLE001 — corrupt/half-wiped cluster; rebuild it
        print(f"   cluster unusable ({exc}); rebuilding a fresh one", file=sys.stderr)
        subprocess.run(["pkill", "-f", f"postgres -D {pgdata}"], check=False)
        time.sleep(2)
        shutil.rmtree(pgdata, ignore_errors=True)
        srv = ensure_ready(pgdata)

    # A fresh initdb ships only the socket-local 'postgres' superuser; the app
    # connects as demo_slot/demo_slot. Docker creates these via POSTGRES_USER/
    # POSTGRES_DB — the local pgserver flow has to do it here. Idempotent.
    with psycopg.connect(srv.get_uri(), autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname = 'demo_slot'").fetchone():
            conn.execute("CREATE ROLE demo_slot LOGIN PASSWORD 'demo_slot' CREATEDB SUPERUSER")
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = 'demo_slot'").fetchone():
            conn.execute("CREATE DATABASE demo_slot OWNER demo_slot")

    print(srv.get_uri())


if __name__ == "__main__":
    main()
