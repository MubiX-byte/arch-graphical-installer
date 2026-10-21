"""Installed root-owned entry point. Never run the GUI as root."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from arch_installer.backend import helper_main
raise SystemExit(helper_main())
