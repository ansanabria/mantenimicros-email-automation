from email_automation.config import Settings
from email_automation.models import ClientRequest, RequestKind, SupplierOffer
from email_automation.services.matching import MatchingService
from email_automation.services.openrouter import OpenRouterClient


class DummyOpenRouter(OpenRouterClient):
    async def complete_json(self, system_prompt, user_content, response_model):
        if response_model.__name__ == "MatchEvaluation":
            return response_model(score=80, rationale="Good fit")
        return response_model(subject="Propuesta de equipos", body="Tenemos una opcion disponible.")


def test_rule_score_rewards_similar_products():
    service = MatchingService(Settings(), DummyOpenRouter(Settings()))
    request = ClientRequest(
        id=1,
        email_id=1,
        client_email="client@example.com",
        summary="Necesito 10 laptops Lenovo ThinkPad con 16GB RAM",
        request_kind=RequestKind.SPECIFIC_PRODUCT,
        product_name="Lenovo ThinkPad",
        quantity_needed=10,
        required_specs={"ram": "16GB"},
    )
    offer = SupplierOffer(
        id=1,
        email_id=1,
        supplier_email="supplier@example.com",
        product_name="Lenovo ThinkPad T14",
        brand="Lenovo",
        model="T14",
        quantity_available=12,
        unit_price=900,
        currency="USD",
        specs={"ram": "16GB", "storage": "512GB SSD"},
    )

    assert service._rule_score(request, offer) >= 70
