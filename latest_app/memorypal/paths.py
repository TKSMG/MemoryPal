import json
import os
import re
import shutil
from pathlib import Path

from .constants import APP_AUTHOR, APP_NAME, DEFAULT_PROFILE


LEGACY_DATA_DIR = Path.home() / "MemoryPalData"


def app_data_dir():
    """Return the platform-specific user data folder for MemoryPal."""
    override = os.environ.get("MEMORYPAL_DATA_DIR")
    if override:
        return Path(override).expanduser()
    try:
        from platformdirs import user_data_path

        return Path(user_data_path(APP_NAME, APP_AUTHOR))
    except Exception:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if os.name == "nt" and local_app_data:
            return Path(local_app_data) / APP_NAME
        return Path.home() / ".local" / "share" / APP_NAME


DATA_DIR = app_data_dir()
PROFILES_DIR = DATA_DIR / "profiles"
PROFILES_CONFIG = DATA_DIR / "profiles.json"


def normalize_profile_name(name):
    return re.sub(r"\s+", " ", name or "").strip()


def slugify_profile(name):
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", normalize_profile_name(name)).strip("-")
    return slug or "profile"


def profile_dir(name):
    directory = PROFILES_DIR / slugify_profile(name)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def migrate_legacy_data():
    """Copy existing home-folder data into the platform data directory once."""
    if LEGACY_DATA_DIR == DATA_DIR or not LEGACY_DATA_DIR.exists():
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    legacy_profiles = LEGACY_DATA_DIR / "profiles"
    legacy_config = LEGACY_DATA_DIR / "profiles.json"

    if legacy_config.exists() and not PROFILES_CONFIG.exists():
        shutil.copy2(legacy_config, PROFILES_CONFIG)

    if legacy_profiles.exists():
        shutil.copytree(legacy_profiles, PROFILES_DIR, dirs_exist_ok=True)

    legacy_file = LEGACY_DATA_DIR / "memorypal-data.json"
    legacy_attach = LEGACY_DATA_DIR / "attachments"
    default_dir = profile_dir(DEFAULT_PROFILE)

    if legacy_file.exists() and not (default_dir / "memorypal-data.json").exists():
        shutil.copy2(legacy_file, default_dir / "memorypal-data.json")
        if legacy_attach.exists():
            shutil.copytree(legacy_attach, default_dir / "attachments", dirs_exist_ok=True)


def load_profiles_config():
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    migrate_legacy_data()
    if not PROFILES_CONFIG.exists():
        config = {"active": DEFAULT_PROFILE, "names": [DEFAULT_PROFILE]}
        PROFILES_CONFIG.write_text(json.dumps(config, indent=2), encoding="utf-8")
        return config
    try:
        config = json.loads(PROFILES_CONFIG.read_text(encoding="utf-8"))
        if not config.get("names"):
            config["names"] = [DEFAULT_PROFILE]
        if config.get("active") not in config["names"]:
            config["active"] = config["names"][0]
        return config
    except (OSError, json.JSONDecodeError):
        return {"active": DEFAULT_PROFILE, "names": [DEFAULT_PROFILE]}


def save_profiles_config(config):
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES_CONFIG.write_text(json.dumps(config, indent=2), encoding="utf-8")


def list_profiles():
    return load_profiles_config()["names"]


def active_profile_name():
    return load_profiles_config()["active"]


def create_profile(name):
    name = normalize_profile_name(name)
    if not name:
        return False, "Enter a profile name."
    config = load_profiles_config()
    if name in config["names"]:
        return False, "A profile with that name already exists."
    config["names"].append(name)
    save_profiles_config(config)
    profile_dir(name)
    return True, ""


def rename_profile(old_name, new_name):
    new_name = normalize_profile_name(new_name)
    if not new_name:
        return False, "Enter a profile name."
    config = load_profiles_config()
    if old_name not in config["names"]:
        return False, "Profile not found."
    if new_name != old_name and new_name in config["names"]:
        return False, "A profile with that name already exists."
    old_dir = profile_dir(old_name)
    new_dir = PROFILES_DIR / slugify_profile(new_name)
    if old_dir != new_dir:
        if new_dir.exists():
            return False, "A profile folder with that name already exists."
        old_dir.rename(new_dir)
    config["names"] = [new_name if item == old_name else item for item in config["names"]]
    if config["active"] == old_name:
        config["active"] = new_name
    save_profiles_config(config)
    return True, ""


def delete_profile(name):
    config = load_profiles_config()
    if name not in config["names"] or len(config["names"]) <= 1:
        return False, "You need at least one profile."
    config["names"].remove(name)
    if config["active"] == name:
        config["active"] = config["names"][0]
    save_profiles_config(config)
    shutil.rmtree(profile_dir(name), ignore_errors=True)
    return True, ""


def set_active_profile(name):
    config = load_profiles_config()
    if name not in config["names"]:
        config["names"].append(name)
    config["active"] = name
    save_profiles_config(config)


def current_data_paths():
    directory = profile_dir(active_profile_name())
    return directory / "memorypal-data.json", directory / "attachments"


_DEFAULT_PROFILE_DIR = PROFILES_DIR / slugify_profile(DEFAULT_PROFILE)
DATA_FILE = _DEFAULT_PROFILE_DIR / "memorypal-data.json"
ATTACHMENT_DIR = _DEFAULT_PROFILE_DIR / "attachments"


def refresh_current_data_paths():
    global DATA_FILE, ATTACHMENT_DIR
    DATA_FILE, ATTACHMENT_DIR = current_data_paths()
    return DATA_FILE, ATTACHMENT_DIR


def switch_active_profile_paths(name):
    set_active_profile(name)
    return refresh_current_data_paths()
