import stripe
import os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
stripe.api_key = "sk_test_51SUdMoEwnNTMkfQfSozdqBY5HjPyzj6kENXBKl9I0dlLrosaNpiPzHZhe0v2t4yCvrGRP6xPwjTitwYirR20dLP5008LstyxzN"
def create_payment_intent(amount: int, metadata: dict = None):
    """
    Crea un PaymentIntent REAL con metadata
    """
    return stripe.PaymentIntent.create(
        amount=amount,
        currency="mxn",
        metadata=metadata or {}
    )