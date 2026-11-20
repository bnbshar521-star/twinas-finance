from datetime import datetime, timedelta, timezone
from fastapi import HTTPException

COOLDOWN_HOURS = 24

def validate_24h_cooldown(last_accumulation_at):
    """
    تتحقق من مرور 24 ساعة كاملة منذ آخر عملية تراكم.
    تقبل last_accumulation_at كـ datetime أو نص ISO أو None.
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
        remaining_seconds = int(remaining.total_seconds())
        hours = remaining_seconds // 3600
        minutes = (remaining_seconds % 3600) // 60
        raise HTTPException(
            status_code=429,
            detail={
                "message": "يجب مرور 24 ساعة كاملة بين كل عملية تراكم وأخرى.",
                "remaining_seconds": remaining_seconds,
                "remaining_formatted": f"{hours}h {minutes}m",
                "next_allowed_at": next_allowed.isoformat(),
            },
        )

    return True
  
