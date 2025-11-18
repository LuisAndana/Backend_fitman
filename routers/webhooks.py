import stripe
stripe.api_key = "sk_test_51SUdMoEwnNTMkfQfSozdqBY5HjPyzj6kENXBKl9I0dlLrosaNpiPzHZhe0v2t4yCvrGRP6xPwjTitwYirR20dLP5008LstyxzN"
from fastapi import APIRouter, Header, Request, HTTPException
from services.payment_service import confirmar_pago

router = APIRouter(prefix="/webhooks/stripe")

STRIPE_WEBHOOK_SECRET = "whsec_xxxxxxxxx"

@router.post("")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
):
    payload = await request.body()

    try:
        # Verificamos firma del webhook
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            STRIPE_WEBHOOK_SECRET
        )

    except Exception as e:
        import traceback
        traceback.print_exc()  # ⬅ Imprime el error real en consola
        raise HTTPException(status_code=400, detail=str(e))

    # Manejo de evento correcto
    if event["type"] == "payment_intent.succeeded":
        data = event["data"]["object"]

        id_pago = data.get("metadata", {}).get("id_pago")

        if not id_pago:
            raise HTTPException(
                status_code=400,
                detail="metadata.id_pago no fue enviado en el PaymentIntent"
            )

        try:
            db = request.state.db  # Recuperamos la sesión de BD
            confirmar_pago(db, id_pago)
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error al confirmar pago: {str(e)}")

    return {"status": "ok"}

