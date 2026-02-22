# REST Python Dev Setup (Windows)

## 1) Create venv (recommended)
From repo root:

py -m venv .venv

## 2) Activate venv
PowerShell:
.\.venv\Scripts\Activate.ps1

CMD:
.\.venv\Scripts\activate.bat

## 3) Install requirements
py -m pip install -U pip
py -m pip install -r python\requirements.txt

## 4) Run validation
py python\validate.py

## If you hit Permission denied
Prefer venv install (steps above). If you still need user install:

py -m pip install --user -r python\requirements.txt
