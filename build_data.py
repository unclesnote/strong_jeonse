#!/usr/bin/env python3
"""Compatibility entrypoint: activate a validated standard dataset."""
import argparse,json,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--dataset');p.add_argument('--asset-root');p.add_argument('--dry-run',action='store_true')
args=p.parse_args()
active_file=root/'config/active-dataset.json'
active=json.loads(active_file.read_text()) if active_file.exists() else {}
dataset=args.dataset or active.get('dataset');asset_root=args.asset_root or active.get('assetRoot')
if not dataset or not asset_root:p.error('먼저 --dataset과 --asset-root를 지정하세요. DATA_GUIDE.md 참고')
command=[sys.executable,str(root/'tools/dataset.py'),'activate','--dataset',dataset,'--asset-root',asset_root]
if args.dry_run:command.append('--dry-run')
raise SystemExit(subprocess.run(command).returncode)
