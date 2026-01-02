"""
Timezone utility for consistent IST timestamps across the application
"""
from datetime import datetime
import pytz

def get_ist_timestamp() -> str:
    """
    Get current timestamp in Indian Standard Time (IST)
    
    Returns:
        ISO format timestamp string in IST timezone
    """
    ist = pytz.timezone('Asia/Kolkata')
    utc_time = datetime.utcnow().replace(tzinfo=pytz.UTC)
    ist_time = utc_time.astimezone(ist)
    return ist_time.isoformat()

def utc_to_ist(utc_datetime: datetime) -> datetime:
    """
    Convert UTC datetime to IST
    
    Args:
        utc_datetime: Datetime in UTC
        
    Returns:
        Datetime in IST timezone
    """
    ist = pytz.timezone('Asia/Kolkata')
    if utc_datetime.tzinfo is None:
        utc_datetime = utc_datetime.replace(tzinfo=pytz.UTC)
    return utc_datetime.astimezone(ist)
