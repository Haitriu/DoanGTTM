import sys
from pathlib import Path
# Allow importing from apps
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from apps.cli.main import cli

if __name__ == "__main__":
    cli()
