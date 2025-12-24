import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.sample_code.tmp_target_1766602052 import calculate_total_price, apply_discount, is_free_shipping, summarize_order

import pytest

if os.getenv('RUN_UI_GENERATED') != '1':
    pytest.skip('ui generated tests are disabled', allow_module_level=True)

def test_calculate_total_price_prints_or_runs(capsys):
    calculate_total_price([], 1.0)
    captured = capsys.readouterr()
    assert 'No items in order' in captured.out

def test_calculate_total_price_typical_returns_value():
    result = calculate_total_price([{'price': 10.0, 'quantity': 1}], 1.0)
    assert result is not None

def test_calculate_total_price_edge_case_returns_value():
    result = calculate_total_price([{'price': 10.0, 'quantity': 1}, {'price': 10.0, 'quantity': 1}], 0.0)
    assert result is not None

def test_calculate_total_price_additional_case_returns_value():
    result = calculate_total_price([{'price': 10.0, 'quantity': 1}], 1.0)
    assert result is not None

def test_calculate_total_price_negative_raises_value_error():
    with pytest.raises(ValueError):
        calculate_total_price([{'price': 10.0, 'quantity': -1}], 1.0)

def test_apply_discount_prints_or_runs(capsys):
    apply_discount(1.0, 'INVALID')
    captured = capsys.readouterr()
    assert 'Invalid coupon code: ' in captured.out

def test_apply_discount_typical_returns_value():
    result = apply_discount(1.0, 'SAVE10')
    assert result is not None

def test_apply_discount_edge_case_returns_value():
    result = apply_discount(0.0, 'INVALID')
    assert result is not None

def test_apply_discount_additional_case_returns_value():
    result = apply_discount(1.0, None)
    assert result is not None

def test_apply_discount_negative_raises_value_error():
    with pytest.raises(ValueError):
        apply_discount(-1.0, 'SAVE10')

def test_is_free_shipping_typical_returns_value():
    result = is_free_shipping(1.0)
    assert result is not None

def test_is_free_shipping_edge_case_returns_value():
    result = is_free_shipping(0.0)
    assert result is not None

def test_summarize_order_typical_returns_value():
    result = summarize_order([{'quantity': 1}])
    assert result is not None

def test_summarize_order_edge_case_returns_value():
    result = summarize_order([{'quantity': 1}, {'quantity': 1}])
    assert result is not None

def test_summarize_order_additional_case_returns_value():
    result = summarize_order([{'quantity': 1}])
    assert result is not None
