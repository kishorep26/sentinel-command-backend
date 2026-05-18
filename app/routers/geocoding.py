from fastapi import APIRouter, HTTPException, Query
import httpx

router = APIRouter(tags=["geocoding"])


@router.get("/search-address")
def search_address(query: str = Query(..., min_length=3)):
    try:
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 5},
            headers={"User-Agent": "sentinel-command-backend/2.0"},
            timeout=10,
        )
        resp.raise_for_status()
        return [
            {"lat": float(r["lat"]), "lon": float(r["lon"]), "address": r["display_name"]}
            for r in resp.json()
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Address search failed: {exc}")


@router.post("/classify-incident")
def classify_incident(data: dict):
    desc = data.get("desc", "").lower()
    if any(w in desc for w in ["fire", "smoke", "burning", "flames"]):
        return {"category": "fire", "confidence": 0.95}
    if any(w in desc for w in ["medical", "injury", "accident", "ambulance", "emergency"]):
        return {"category": "medical", "confidence": 0.92}
    if any(w in desc for w in ["theft", "robbery", "crime", "police", "assault", "break"]):
        return {"category": "crime", "confidence": 0.90}
    return {"category": "other", "confidence": 0.75}
