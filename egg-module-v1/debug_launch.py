import traceback
import sys
import os

try:
    with open("crash_debug.log", "w") as f:
        f.write("Starting crash debug...\n")
        try:
            from main import app, engine
            f.write("Imports successful. Running exec...\n")
            sys.exit(app.exec())
        except Exception as e:
            f.write("CRASH DETECTED:\n")
            f.write(traceback.format_exc())
            print(traceback.format_exc())
except Exception as global_e:
    with open("global_crash.log", "w") as f:
        f.write(traceback.format_exc())
