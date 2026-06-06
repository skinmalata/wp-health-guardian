import os
import datetime

from google.cloud import firestore

FIRESTORE_DATABASE_ID = os.environ.get("FIRESTORE_DATABASE_ID", None)
FIRESTORE_COLLECTION = os.environ.get("FIRESTORE_COLLECTION", "health-checks")


def get_firestore_client():
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    if not project:
        return None
    try:
        if FIRESTORE_DATABASE_ID:
            return firestore.AsyncClient(
                project=project, database_id=FIRESTORE_DATABASE_ID
            )
        return firestore.AsyncClient(project=project)
    except Exception:
        return None


_db = None


async def ensure_db():
    global _db
    if _db is None:
        _db = get_firestore_client()
    return _db


async def save_health_check(report: dict):
    db = await ensure_db()
    if db is None:
        return None

    doc = {
        "site_url": report.get("site_url", ""),
        "timestamp": firestore.SERVER_TIMESTAMP,
        "status": report.get("summary", {}).get("status", "unknown"),
        "score": report.get("summary", {}).get("score", 0),
        "issues_found": report.get("summary", {}).get("issues_found", 0),
        "checks": report.get("checks", []),
        "recommendations": report.get("recommendations", []),
    }

    doc_ref = db.collection(FIRESTORE_COLLECTION).document()
    await doc_ref.set(doc)
    return doc_ref.id


async def get_check_history(
    site_url: str = None, limit: int = 20
) -> list:
    db = await ensure_db()
    if db is None:
        return []

    try:
        query = (
            db.collection(FIRESTORE_COLLECTION)
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )

        if site_url:
            query = query.where("site_url", "==", site_url)

        docs = await query.get()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            ts = data.get("timestamp")
            if isinstance(ts, datetime.datetime):
                data["timestamp"] = ts.isoformat()
            results.append(data)
        return results

    except Exception:
        return []


async def get_recent_checks(limit: int = 10) -> list:
    return await get_check_history(site_url=None, limit=limit)


# === Monitored Sites (for dashboard) ===

MONITORED_SITES_COLLECTION = "monitored-sites"


async def add_monitored_site(url: str) -> dict:
    db = await ensure_db()
    if db is None:
        return {"error": "Firestore not available"}

    try:
        existing = await get_monitored_sites()
        for site in existing:
            if site["url"] == url:
                return {"error": "Site already monitored", "id": site["id"]}

        doc = {
            "url": url,
            "added_at": firestore.SERVER_TIMESTAMP,
        }
        doc_ref = db.collection(MONITORED_SITES_COLLECTION).document()
        await doc_ref.set(doc)
        return {"success": True, "id": doc_ref.id, "url": url}
    except Exception as e:
        return {"error": str(e)}


async def remove_monitored_site(site_id: str) -> dict:
    db = await ensure_db()
    if db is None:
        return {"error": "Firestore not available"}
    try:
        await db.collection(MONITORED_SITES_COLLECTION).document(site_id).delete()
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


async def get_monitored_sites() -> list:
    db = await ensure_db()
    if db is None:
        return []
    try:
        docs = await db.collection(MONITORED_SITES_COLLECTION).order_by("added_at").get()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            ts = data.get("added_at")
            if isinstance(ts, datetime.datetime):
                data["added_at"] = ts.isoformat()
            results.append(data)
        return results
    except Exception:
        return []


async def get_check_by_id(doc_id: str) -> dict | None:
    db = await ensure_db()
    if db is None:
        return None
    try:
        doc = await db.collection(FIRESTORE_COLLECTION).document(doc_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data["id"] = doc.id
        ts = data.get("timestamp")
        if isinstance(ts, datetime.datetime):
            data["timestamp"] = ts.isoformat()
        return data
    except Exception:
        return None


async def get_dashboard() -> list:
    db = await ensure_db()
    if db is None:
        return []
    try:
        sites = await get_monitored_sites()
        if not sites:
            return []
        site_urls = [s["url"] for s in sites]
        latest = []
        for site_url in site_urls:
            docs = await db.collection(FIRESTORE_COLLECTION).where("site_url", "==", site_url).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(1).get()
            for doc in docs:
                data = doc.to_dict()
                ts = data.get("timestamp")
                if isinstance(ts, datetime.datetime):
                    data["timestamp"] = ts.isoformat()
                data["id"] = doc.id
                latest.append(data)
        return latest
    except Exception:
        return []
