

# --- APPLAYLIST PYTEST DUPLICATE GUARD ---
collect_ignore_glob = [*globals().get("collect_ignore_glob", []), "* 2.py", "**/* 2.py"]
