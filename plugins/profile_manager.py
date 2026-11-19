"""
Re-export profile_manager from utils.profile_manager for backward compatibility.
"""

from utils.profile_manager import ProfileManager, profile_manager

__all__ = ["ProfileManager", "profile_manager"]
