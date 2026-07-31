# app/scripts/backfill_stock_item_drug_links.py
from __future__ import annotations

"""
Backfill: link existing DRUG stock items to the drug formulary.

Harmonises inventory with the drug catalogue after the fact. For each
DRUG-type ``InventoryStockItem`` that has no ``drug_id``, it tries to match a
``Drug`` by SKU (case-insensitive) and then by exact name. On a match it sets
``drug_id`` and fills any missing descriptive fields (unit of measure, reorder
level) from the drug — the catalogue stays the single source of truth. Rows
that can't be matched are reported so they can be reviewed by hand.

Usage (mirrors the security seed's CLI):

    # current/default database
    python -m app.scripts.backfill_stock_item_drug_links

    # a specific database URL
    python -m app.scripts.backfill_stock_item_drug_links --db-url postgresql://...

    # every provisioned tenant
    python -m app.scripts.backfill_stock_item_drug_links --all-tenants

Add --apply to write changes; without it the script runs as a DRY RUN and only
reports what it *would* do.
"""

import argparse
import re

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.cryptography import decrypt_string
from app.core.database import SessionLocal, get_master_engine
from app.core.enums import InventoryItemType
from app.models.all_models import Drug, InventoryStockItem, Tenant


_SYNONYMS = {
    "frusemide": "furosemide",
    "lignocaine": "lidocaine",
    "adrenaline": "epinephrine",
    "noradrenaline": "norepinephrine",
    "salbutamol": "albuterol",
    "paracetamol": "acetaminophen",
}


def _normalize_key(name: str) -> frozenset:
    """
    Format-insensitive token-set key: strips volume fragments (e.g. '/3ml',
    '20ml', '/ml'), applies a small synonym map, and returns the remaining
    tokens. Names differing only in how volume/strength is written collapse
    to the same key.
    """
    t = (name or "").lower()
    t = re.sub(r"/\s*\d+(?:\.\d+)?\s*ml", " ", t)
    t = re.sub(r"/\s*ml", " ", t)
    t = re.sub(r"\b\d+(?:\.\d+)?\s*ml\b", " ", t)
    t = re.sub(r"[^a-z0-9%.]+", " ", t)
    return frozenset(_SYNONYMS.get(tok, tok) for tok in t.split() if tok)


def backfill(db: Session, *, apply: bool = False) -> dict:
    """Link unlinked DRUG stock items to drugs. Returns a summary dict."""
    drugs = db.query(Drug).filter(Drug.is_deleted.is_(False)).all()
    by_sku = {d.sku.strip().upper(): d for d in drugs if d.sku}
    by_name = {d.name.strip().upper(): d for d in drugs}

    _norm: dict = {}
    for d in drugs:
        _norm.setdefault(_normalize_key(d.name), []).append(d)
    by_norm = {k: v[0] for k, v in _norm.items() if len(v) == 1}

    items = (
        db.query(InventoryStockItem)
        .filter(
            InventoryStockItem.is_deleted.is_(False),
            InventoryStockItem.item_type == InventoryItemType.DRUG,
            InventoryStockItem.drug_id.is_(None),
        )
        .all()
    )

    linked = 0
    enriched = 0
    unmatched: list[dict] = []

    for it in items:
        drug = None
        if it.sku and it.sku.strip():
            drug = by_sku.get(it.sku.strip().upper())
        if drug is None and it.item_name:
            drug = by_name.get(it.item_name.strip().upper())
        if drug is None and it.item_name:
            drug = by_norm.get(_normalize_key(it.item_name))
        if drug is None:
            unmatched.append({"id": it.id, "item_name": it.item_name, "sku": it.sku})
            continue

        it.drug_id = drug.id
        linked += 1
        changed = False
        if (not it.sku or not it.sku.strip()) and drug.sku:
            it.sku = drug.sku
            changed = True
        if (not it.unit_of_measure or not it.unit_of_measure.strip()) and drug.dosage_form:
            it.unit_of_measure = drug.dosage_form
            changed = True
        if it.reorder_level is None and drug.reorder_level is not None:
            it.reorder_level = drug.reorder_level
            changed = True
        if changed:
            enriched += 1
        if apply:
            db.add(it)

    if apply:
        db.commit()

    return {
        "candidates": len(items),
        "linked": linked,
        "enriched": enriched,
        "unmatched": len(unmatched),
        "unmatched_rows": unmatched,
        "applied": apply,
    }


def _report(label: str, summary: dict) -> None:
    print(f"\n[{label}] mode={'APPLY' if summary['applied'] else 'DRY-RUN'}")
    print(
        f"  candidates={summary['candidates']} "
        f"linked={summary['linked']} enriched={summary['enriched']} "
        f"unmatched={summary['unmatched']}"
    )
    for row in summary["unmatched_rows"][:50]:
        print(f"    UNMATCHED  #{row['id']}  {row['item_name']!r}  sku={row['sku']!r}")
    if summary["unmatched"] > 50:
        print(f"    ... and {summary['unmatched'] - 50} more")


def _run_cli() -> None:
    parser = argparse.ArgumentParser(description="Backfill stock-item → drug links.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all-tenants", action="store_true", help="Run for all provisioned tenants.")
    group.add_argument("--db-url", type=str, help="Run against a specific database URL.")
    parser.add_argument("--apply", action="store_true", help="Persist changes (default is a dry run).")
    args = parser.parse_args()

    if args.all_tenants:
        print("--- Fleet-wide stock↔drug backfill ---")
        master_engine = get_master_engine()
        with Session(master_engine) as master_db:
            tenants = master_db.query(Tenant).filter(Tenant.is_provisioned == True).all()  # noqa: E712
            tenant_data = [{"name": t.name, "code": t.code, "conn": t.db_connection_string} for t in tenants]
        for t in tenant_data:
            if not t["conn"]:
                continue
            try:
                engine = create_engine(decrypt_string(t["conn"]))
                with Session(engine) as tdb:
                    _report(f"{t['name']} ({t['code']})", backfill(tdb, apply=args.apply))
                engine.dispose()
            except Exception as e:  # pragma: no cover
                print(f"  [X] {t['code']}: {e}")
        return

    if args.db_url:
        engine = create_engine(args.db_url)
        db = sessionmaker(bind=engine)()
    else:
        db = SessionLocal()
    try:
        _report("single-db", backfill(db, apply=args.apply))
    finally:
        db.close()


if __name__ == "__main__":
    _run_cli()
