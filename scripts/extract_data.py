#!/usr/bin/env python3
"""Compatibility entrypoint for configured XLSX extraction; run import_xlsx.py for options."""
import os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
pan=os.environ.get('LH_PAN_ID','2015122300020927')
command=[sys.executable,str(root/'scripts/import_xlsx.py'),'--config',str(root/'config/lh-current.json'),'--output',str(root/'data/datasets'/pan/'dataset.json'),'--extract-only',str(root/'data/intermediate'/pan/'source-data.json')]
raise SystemExit(subprocess.run(command+sys.argv[1:]).returncode)
