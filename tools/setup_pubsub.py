import os
from google.cloud import pubsub_v1

PROJECT_ID = os.getenv("AGENT_MKT_PROJECT_ID")
if not PROJECT_ID:
    print("❌ AGENT_MKT_PROJECT_ID environment variable is not set.")
    exit(1)

def setup_pubsub():
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()
    
    topics = ["market.discovery", "market.negotiation"]
    subscriptions = {
        "seller-sub-discovery": "market.discovery",
        "buyer-sub-negotiation": "market.negotiation",
        "seller-sub-negotiation": "market.negotiation"
    }
    
    for topic_id in topics:
        topic_path = publisher.topic_path(PROJECT_ID, topic_id)
        try:
            publisher.create_topic(name=topic_path)
            print(f"✅ Created topic: {topic_id}")
        except Exception as e:
            if "AlreadyExists" in str(e):
                print(f"ℹ️ Topic {topic_id} already exists")
            else:
                print(f"❌ Error creating topic {topic_id}: {e}")
                
    for sub_id, topic_id in subscriptions.items():
        sub_path = subscriber.subscription_path(PROJECT_ID, sub_id)
        topic_path = publisher.topic_path(PROJECT_ID, topic_id)
        try:
            subscriber.create_subscription(name=sub_path, topic=topic_path)
            print(f"✅ Created subscription: {sub_id}")
        except Exception as e:
            if "AlreadyExists" in str(e):
                print(f"ℹ️ Subscription {sub_id} already exists")
            else:
                print(f"❌ Error creating subscription {sub_id}: {e}")

if __name__ == "__main__":
    setup_pubsub()
