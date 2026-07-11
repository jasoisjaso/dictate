"""Compiled-app entry point: makes src a real package so its relative
imports work under Nuitka (main.py alone would be __main__ and they'd fail)."""
from src.main import main

main()
