"""PyInstaller 단일 exe 진입점.

패키지 상대 import 문제를 피하기 위해 최상위 스크립트에서 cli.main을 호출한다.
"""
from __future__ import annotations

import sys

from electralens.cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
