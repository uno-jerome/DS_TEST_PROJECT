import json
import os


def default_shop_state():
    return {
        "remember_me": False,
        "remembered_email": "",
        "remembered_login_identifier": "",
        "cart_cache": {},
    }


def load_shop_state(state_file_path):
    if not os.path.exists(state_file_path):
        return default_shop_state()

    try:
        with open(state_file_path, "r", encoding="utf-8") as state_file:
            loaded_state = json.load(state_file)
            if not isinstance(loaded_state, dict):
                return default_shop_state()

            loaded_state.setdefault("remember_me", False)
            loaded_state.setdefault("remembered_email", "")
            loaded_state.setdefault("remembered_login_identifier", loaded_state.get("remembered_email", ""))
            loaded_state.setdefault("cart_cache", {})

            if not isinstance(loaded_state["cart_cache"], dict):
                loaded_state["cart_cache"] = {}

            return loaded_state
    except Exception:
        return default_shop_state()


def save_shop_state(state_file_path, state_data):
    try:
        with open(state_file_path, "w", encoding="utf-8") as state_file:
            json.dump(state_data, state_file, indent=2)
        return True
    except Exception:
        return False
