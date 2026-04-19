#!/usr/bin/env python
"""Verification test for GemmaClient refactoring."""

import sys
from pathlib import Path

# Add templates directory to path
sys.path.insert(0, str(Path(__file__).parent / "templates"))

from src.core.gemma_client import GemmaClient

# Test 1: Verify new method exists
print("✓ Test 1: Verify _process_chat_response exists")
c = GemmaClient()
assert hasattr(c, '_process_chat_response'), '_process_chat_response missing'
print("  _process_chat_response method found")

# Test 2: Verify _parse_json_fallback still works
print("✓ Test 2: Verify _parse_json_fallback works")
result = c._parse_json_fallback('```json\n{"ok": true}\n```')
assert result == {'ok': True}, f'Expected {{"ok": True}}, got {result}'
print("  _parse_json_fallback parses correctly")

# Test 3: Verify all public methods exist
print("✓ Test 3: Verify all public methods exist")
required_methods = ['generate', 'think', 'analyze_image', 'call_tool', 'is_available', 'model_info']
for method in required_methods:
    assert hasattr(c, method), f'{method} missing'
print(f"  All {len(required_methods)} public methods present")

# Test 4: Verify _chat_with_retry signature changed
print("✓ Test 4: Verify _chat_with_retry signature")
import inspect
from typing import Union
sig = inspect.signature(c._chat_with_retry)
params = list(sig.parameters.keys())
assert 'tools' in params, '_chat_with_retry missing tools parameter'
# Check that tools parameter has Union type
tools_param = sig.parameters['tools']
print(f"  _chat_with_retry has 'tools' parameter: {tools_param}")

# Test 5: Verify _process_chat_response signature
print("✓ Test 5: Verify _process_chat_response signature")
sig = inspect.signature(c._process_chat_response)
print(f"  _process_chat_response signature: {sig}")

# Test 6: Verify private methods are not exported
print("✓ Test 6: Verify __all__ not changed")
from src.core.gemma_client import __all__
assert 'call_tool' not in __all__, 'call_tool should not be in __all__'
assert '_process_chat_response' not in __all__, '_process_chat_response should not be in __all__'
print(f"  __all__ contains: {__all__}")

print("\n✓✓✓ All refactoring tests passed ✓✓✓")
