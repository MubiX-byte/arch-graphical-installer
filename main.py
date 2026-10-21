import argparse
import json
import sys
from arch_installer.config import Config
from arch_installer.plan import summary

def main():
    parser = argparse.ArgumentParser(description="Arch Graphical Installer")
    parser.add_argument("--dry-run", metavar="CONFIG_JSON", help="Print plan only; no root, disk writes or commands")
    args = parser.parse_args()
    if args.dry_run:
        sys.stdout.reconfigure(encoding="utf-8")
        with open(args.dry_run, encoding="utf-8") as file:
            config = Config(**json.load(file))
        print(json.dumps(summary(config), indent=2, ensure_ascii=False))
    else:
        from arch_installer.gui import launch
        launch()

if __name__ == "__main__":
    main()
