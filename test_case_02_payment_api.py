from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import logging
import time

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# Demo data only; this is intentionally insecure test code.
orders = {
    101: {
        "user_id": 1,
        "total": 100.00,
        "status": "pending",
        "paid": False,
    },
    102: {
        "user_id": 2,
        "total": 250.00,
        "status": "pending",
        "paid": False,
    },
}

class PaymentRequest(BaseModel):
    order_id: int
    amount: float
    discount_percent: float = 0


@app.post("/pay")
def pay(
    request: PaymentRequest,
    x_user_id: int = Header(...),
):
    order = orders.get(request.order_id)

    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    # Bug: the request does not verify that this user owns the order.
    logging.info(
        "Processing order %s for user %s",
        request.order_id,
        x_user_id,
    )

    # Bug: trusts the amount supplied by the client.
    amount = request.amount

    # Bug: discount is not validated or capped.
    amount = amount * (1 - request.discount_percent / 100)

    # Bug: simulates a slow external payment call.
    time.sleep(0.2)

    # Bug: repeated requests can process an already-paid order.
    order["paid"] = True
    order["status"] = "paid"

    # Bug: logs potentially sensitive transaction information.
    logging.info(
        "Payment completed: order=%s amount=%s user=%s",
        request.order_id,
        amount,
        x_user_id,
    )

    return {
        "message": "Payment successful",
        "order_id": request.order_id,
        "amount_charged": amount,
        "internal_order": order,
    }
