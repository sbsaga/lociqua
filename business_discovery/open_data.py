"""Import only data for which the operator records a licence or permission basis."""
from __future__ import annotations
import argparse
from pathlib import Path
from .importers import import_csv
from .storage import CompanyStore
def main() -> None:
 p=argparse.ArgumentParser();p.add_argument('csv',type=Path);p.add_argument('--source',required=True);p.add_argument('--permission-basis',required=True);p.add_argument('--license-note',required=True);p.add_argument('--database',default='business_discovery.db');a=p.parse_args();s=CompanyStore(a.database);s.register_source(a.source,'open_data',a.permission_basis,a.license_note);r=import_csv(a.csv.read_bytes(),s,a.source);print(f'accepted={r.accepted} rejected={r.rejected}')
if __name__ == '__main__': main()
