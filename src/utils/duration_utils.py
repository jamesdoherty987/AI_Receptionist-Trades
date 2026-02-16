"""
Duration formatting utilities for human-readable output.
"""


def format_duration(minutes: int) -> str:
    """
    Format duration in minutes to human-readable string.
    
    Args:
        minutes: Duration in minutes
        
    Returns:
        Human-readable duration string (e.g., "2 hours", "1 day", "2 weeks")
    """
    if not minutes or minutes <= 0:
        return ""
    
    # Define time units
    MINUTES_PER_HOUR = 60
    MINUTES_PER_DAY = 1440  # 24 * 60
    MINUTES_PER_WEEK = 10080  # 7 * 24 * 60
    
    # Check for exact matches first for cleaner output
    duration_labels = {
        30: "30 mins",
        60: "1 hour",
        90: "1.5 hours",
        120: "2 hours",
        150: "2.5 hours",
        180: "3 hours",
        210: "3.5 hours",
        240: "4 hours",
        270: "4.5 hours",
        300: "5 hours",
        330: "5.5 hours",
        360: "6 hours",
        390: "6.5 hours",
        420: "7 hours",
        450: "7.5 hours",
        480: "8 hours",
        1440: "1 day",
        2880: "2 days",
        4320: "3 days",
        5760: "4 days",
        7200: "5 days",
        8640: "6 days",
        10080: "1 week",
        20160: "2 weeks",
        30240: "3 weeks",
        40320: "4 weeks",
    }
    
    if minutes in duration_labels:
        return duration_labels[minutes]
    
    # Calculate for non-standard durations
    weeks = minutes // MINUTES_PER_WEEK
    remaining = minutes % MINUTES_PER_WEEK
    days = remaining // MINUTES_PER_DAY
    remaining = remaining % MINUTES_PER_DAY
    hours = remaining // MINUTES_PER_HOUR
    mins = remaining % MINUTES_PER_HOUR
    
    parts = []
    if weeks > 0:
        parts.append(f"{weeks} week{'s' if weeks > 1 else ''}")
    if days > 0:
        parts.append(f"{days} day{'s' if days > 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if mins > 0:
        parts.append(f"{mins} min{'s' if mins > 1 else ''}")
    
    return " ".join(parts) if parts else "0 mins"


def is_multi_day_duration(minutes: int) -> bool:
    """
    Check if duration spans multiple days.
    
    Args:
        minutes: Duration in minutes
        
    Returns:
        True if duration is 1 day or more
    """
    return minutes >= 1440  # 24 hours = 1440 minutes
