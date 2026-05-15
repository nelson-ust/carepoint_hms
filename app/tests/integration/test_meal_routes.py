# app/tests/integration/test_meal_routes.py
from __future__ import annotations

"""Integration tests for Meal Management API."""

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_meal_catalog_access(client: AsyncClient, admin_token_headers):
    """Verify that we can list and create meal types."""
    # 1. List meal types
    response = await client.get("/api/v1/meals/types", headers=admin_token_headers)
    assert response.status_code == status.HTTP_200_OK
    
    # 2. Create a meal type
    payload = {
        "name": "Standard Inpatient Breakfast",
        "code": "ST-BKT",
        "description": "Standard breakfast for all inpatients.",
        "base_price": 450.00
    }
    response = await client.post("/api/v1/meals/types", json=payload, headers=admin_token_headers)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["code"] == payload["code"]


@pytest.mark.asyncio
async def test_meal_order_lifecycle(client: AsyncClient, admin_token_headers):
    """Verify placing an order and marking it as served."""
    # Setup: Create a meal type first
    mt_payload = {"name": "Lunch", "code": "LCH", "base_price": 1000.00}
    mt_res = await client.post("/api/v1/meals/types", json=mt_payload, headers=admin_token_headers)
    mt_id = mt_res.json()["id"]

    # In a real test, we'd need a valid visit_id and patient_id. 
    # For this smoke test, we assume ID 1 exists from conftest seeds.
    order_payload = {
        "visit_id": 1,
        "patient_id": 1,
        "meal_type_id": mt_id,
        "recipient_type": "PATIENT",
        "quantity": 1.0,
        "notes": "No salt"
    }
    
    # 1. Place Order
    response = await client.post("/api/v1/meals/orders", json=order_payload, headers=admin_token_headers)
    assert response.status_code == status.HTTP_201_CREATED
    order_id = response.json()["meal_order"]["id"]
    
    # 2. List Orders
    response = await client.get("/api/v1/meals/orders", headers=admin_token_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["count"] >= 1

    # 3. Serve Meal (Triggers Billing)
    response = await client.post(f"/api/v1/meals/orders/{order_id}/serve", headers=admin_token_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["meal_order"]["status"] == "SERVED"
