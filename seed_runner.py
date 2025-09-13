#!/usr/bin/env python3
"""
Simple runner for the seed script
"""
import asyncio
import sys
import os

# Add current directory to Python path
sys.path.insert(0, '/app')

from scripts.seed_data import main

if __name__ == "__main__":
    asyncio.run(main()) 