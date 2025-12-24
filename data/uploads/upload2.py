"""
order_utils.py

E-ticaret siparişleri için yardımcı fonksiyonlar.
Bu dosya test üretim sistemi için bilinçli olarak
çeşitli edge-case'ler içerir.
"""

from typing import List, Dict


def calculate_total_price(items: List[Dict], tax_rate: float = 0.18) -> float:
    """
    Sipariş toplam tutarını hesaplar.

    items: [{"price": float, "quantity": int}]
    tax_rate: KDV oranı
    """
    if not items:
        print("No items in order")
        return 0.0

    subtotal = 0.0
    for item in items:
        if item["quantity"] < 0:
            raise ValueError("Quantity cannot be negative")

        subtotal += item["price"] * item["quantity"]

    total = subtotal * (1 + tax_rate)
    return round(total, 2)


def apply_discount(total_price: float, coupon_code: str | None) -> float:
    """
    Kupon koduna göre indirim uygular.
    """
    if total_price < 0:
        raise ValueError("Total price cannot be negative")

    if not coupon_code:
        return total_price

    coupon_code = coupon_code.upper()

    if coupon_code == "SAVE10":
        return round(total_price * 0.9, 2)
    elif coupon_code == "SAVE50":
        return round(total_price * 0.5, 2)
    else:
        print(f"Invalid coupon code: {coupon_code}")
        return total_price


def is_free_shipping(total_price: float) -> bool:
    """
    500 TL üzeri siparişlerde ücretsiz kargo.
    """
    return total_price >= 500


def summarize_order(items: List[Dict]) -> str:
    """
    Sipariş özeti döner.
    """
    if not items:
        return "Empty order"

    total_quantity = sum(item["quantity"] for item in items)
    return f"Order contains {len(items)} items, total quantity: {total_quantity}"
