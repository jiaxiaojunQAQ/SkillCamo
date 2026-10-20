# Copyright 2026
#
# Main entry point for adversarial skill_camo CLI.

"""
Main entry point - loads .env before importing the CLI module.
"""

import os
import sys
from pathlib import Path


def _load_root_env():
    """Load .env from project root directory"""
    # Method 1: Check current working directory first (most reliable)
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        env_file = cwd_env
    else:
        # Method 2: Try using __file__ from the main module
        try:
            import __main__
            # When running as module, check for original file
            if hasattr(__main__, '__file__'):
                main_file = Path(__main__.__file__).resolve()
                current = main_file.parent
                while current != current.parent:
                    test_env = current / ".env"
                    if test_env.exists():
                        env_file = test_env
                        break
                    current = current.parent
        except:
            pass

    # Load environment variables
    if env_file and env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                # Remove quotes
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                os.environ[key] = value


# Load .env before importing CLI
_load_root_env()

# Now import and run CLI
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
