
from pydantic import ValidationError
import sys
import os

# Add parent directory to path to import api_server
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_server import MarketRequest, NegotiationAction, UserFeedbackRequest

def test_market_request():
    print("Testing MarketRequest...")
    try:
        # Valid
        MarketRequest(item="A" * 10, max_budget=100)
        # Invalid (Too long)
        try:
            MarketRequest(item="A" * 101, max_budget=100)
            print("❌ MarketRequest failed to catch long item string")
        except ValidationError:
            print("✅ MarketRequest caught long item string")
    except Exception as e:
        print(f"❌ Unexpected error in MarketRequest: {e}")

def test_negotiation_action():
    print("Testing NegotiationAction...")
    try:
        # Valid
        NegotiationAction(
            negotiation_id="1", offer_id="1", sender_id="1", receiver_id="1", action="PROPOSE", 
            reasoning="A" * 999
        )
        # Invalid (Too long reasoning)
        try:
            NegotiationAction(
                negotiation_id="1", offer_id="1", sender_id="1", receiver_id="1", action="PROPOSE",
                reasoning="A" * 1001
            )
            print("❌ NegotiationAction failed to catch long reasoning string")
        except ValidationError:
            print("✅ NegotiationAction caught long reasoning string")
    except Exception as e:
        print(f"❌ Unexpected error in NegotiationAction: {e}")

def test_user_feedback():
    print("Testing UserFeedbackRequest...")
    try:
        # Valid
        UserFeedbackRequest(negotiation_id="1", rating=5, comment="A" * 499)
        # Invalid (Too long comment)
        try:
            UserFeedbackRequest(negotiation_id="1", rating=5, comment="A" * 501)
            print("❌ UserFeedbackRequest failed to catch long comment string")
        except ValidationError:
            print("✅ UserFeedbackRequest caught long comment string")
    except Exception as e:
        print(f"❌ Unexpected error in UserFeedbackRequest: {e}")

if __name__ == "__main__":
    test_market_request()
    test_negotiation_action()
    test_user_feedback()
