# ElectraLens AI — 단일 Windows 실행파일(dist\ElectraLensAI.exe) 빌드 스크립트.
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# 파이썬 인터프리터: 환경변수 ELECTRALENS_PYTHON로 재정의 가능, 기본은 PATH의 python.
$python = if ($env:ELECTRALENS_PYTHON) { $env:ELECTRALENS_PYTHON } else { "python" }

# 아이콘 생성
& $python tools\generate_icon.py

# 빌드 의존성(PyInstaller + Pillow + NumPy)을 격리 폴더에 설치
$buildTools = Join-Path $root "build_tools"
if (-not (Test-Path (Join-Path $buildTools "PyInstaller"))) {
  & $python -m pip install --target $buildTools -r requirements-build.txt
}

$env:PYTHONPATH = $buildTools
$argsList = @(
  "--noconfirm",
  "--clean",
  "--onefile",
  "--windowed",
  "--name", "ElectraLensAI",
  "--icon", "electralens/assets/electralens.ico",
  "--add-data", "electralens/assets/electralens.ico;electralens/assets",
  "--hidden-import", "PIL._tkinter_finder",
  "electralens_app.py"
)
$code = "from PyInstaller.__main__ import run; run($($argsList | ConvertTo-Json -Compress))"
& $python -c $code

Write-Host "Built dist\ElectraLensAI.exe"
