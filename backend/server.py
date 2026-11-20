from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Twinas Finance Accumulation API")

COOLDOWN_HOURS = 24
DATA_FILE = Path(__file__).resolve().parent / "users_data.json"


class AccumulateRequest(BaseModel):
    user_id: str
    amount: float = 1.0


def _load_users() -> dict:
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_users(data: dict) -> None:
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def validate_24h_cooldown(last_accumulation_at) -> bool:
    """
    تتحقق من مرور 24 ساعة كاملة منذ آخر عملية تراكم.
    إذا لم يمضِ 24 ساعة ترفع استثناء 429 مع الوقت المتبقي.
    """
    if not last_accumulation_at:
        return True

    if isinstance(last_accumulation_at, str):
        last_dt = datetime.fromisoformat(last_accumulation_at.replace("Z", "+00:00"))
    else:
        last_dt = last_accumulation_at

    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    next_allowed = last_dt + timedelta(hours=COOLDOWN_HOURS)

    if now < next_allowed:
        remaining = next_allowed - now
        remaining_seconds = max(0, int(remaining.total_seconds()))
        hours = remaining_seconds // 3600
        minutes = (remaining_seconds % 3600) // 60
        seconds = remaining_seconds % 60
        raise HTTPException(
            status_code=429,
            detail={
                "message": "A full 24-hour cooldown is required between accumulation requests.",
                "remaining_seconds": remaining_seconds,
                "remaining_formatted": f"{hours}h {minutes}m {seconds}s",
                "next_allowed_at": next_allowed.isoformat(),
            },
        )

    return True


@app.post("/accumulate")
def accumulate_balance(payload: AccumulateRequest):
    users = _load_users()
    user = users.get(payload.user_id) or {
        "user_id": payload.user_id,
        "balance": 0.0,
        "last_accumulation_at": None,
    }

    # 1. فحص مرور 24 ساعة من آخر كبسة
    validate_24h_cooldown(user.get("last_accumulation_at"))

    # 2. إضافة التراكم وتحديث وقت آخر كبسة بالـ UTC
    now_iso = datetime.now(timezone.utc).isoformat()
    user["balance"] = round(float(user.get("balance", 0.0)) + float(payload.amount), 4)
    user["last_accumulation_at"] = now_iso

    users[payload.user_id] = user
    _save_users(users)

    next_allowed_iso = (
        datetime.fromisoformat(now_iso) + timedelta(hours=COOLDOWN_HOURS)
    ).isoformat()

    return {
        "status": "accumulated",
        "user_id": user["user_id"],
        "balance": user["balance"],
        "last_accumulation_at": user["last_accumulation_at"],
        "next_allowed_at": next_allowed_iso,
    }


@app.get("/accumulate/status/{user_id}")
def accumulation_status(user_id: str):
    users = _load_users()
    user = users.get(user_id)
    last_acc = user.get("last_accumulation_at") if user else None
    balance = float(user.get("balance", 0.0)) if user else 0.0

    if not last_acc:
        return {
            "user_id": user_id,
            "balance": balance,
            "can_accumulate": True,
            "remaining_seconds": 0,
            "next_allowed_at": None,
        }

    last_dt = datetime.fromisoformat(last_acc.replace("Z", "+00:00"))
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    next_allowed = last_dt + timedelta(hours=COOLDOWN_HOURS)
    remaining_seconds = max(0, int((next_allowed - now).total_seconds()))

    return {
        "user_id": user_id,
        "balance": balance,
        "can_accumulate": remaining_seconds == 0,
        "remaining_seconds": remaining_seconds,
        "next_allowed_at": next_allowed.isoformat(),
    }
    
