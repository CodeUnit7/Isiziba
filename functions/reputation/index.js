const { onDocumentCreated } = require("firebase-functions/v2/firestore");
const { getFirestore, FieldValue } = require("firebase-admin/firestore");
const admin = require("firebase-admin");

admin.initializeApp();
const db = getFirestore();

/**
 * Triggered when a new transaction is created in the 'transactions' collection.
 * Calculates the new reputation score for the seller based on:
 * 1. The rating (1-5 stars).
 * 2. The relationship diversity (anti-wash trading).
 * 3. Time decay of previous reputation.
 */
exports.updateAgentReputation = onDocumentCreated("transactions/{txId}", async (event) => {
    const snapshot = event.data;
    if (!snapshot) {
        console.log("No data associated with the event");
        return;
    }

    const data = snapshot.data();
    const { buyer_id, seller_id, rating } = data;

    // Constants for Decay and Protection
    const MAX_PARTNER_PERCENTAGE = 0.20; // Max 20% of transactions from same partner
    const MIN_TX_THRESHOLD = 10;        // Grace period for new agents
    const HALFLIFE_DAYS = 30;           // Score loses 50% weight every 30 days
    const LAMBDA = Math.LN2 / HALFLIFE_DAYS; 

    try {
        const sellerRef = db.collection("agents").doc(seller_id);
        const sellerDoc = await sellerRef.get();
        
        const now = Date.now();
        // Default values for new agents
        const sellerData = sellerDoc.data() || { 
            global_reputation: 50, 
            total_transactions: 0,
            last_updated: admin.firestore.Timestamp.now() 
        };

        // 1. TIME DECAY CALCULATION
        const lastUpdateMs = sellerData.last_updated.toMillis();
        const daysSinceLastUpdate = (now - lastUpdateMs) / (1000 * 60 * 60 * 24);
        
        // N(t) = N0 * e^(-λt)
        const decayFactor = Math.exp(-LAMBDA * daysSinceLastUpdate);
        
        // Decay towards baseline of 50
        const baseline = 50;
        let decayedRep = baseline + (sellerData.global_reputation - baseline) * decayFactor;

        // 2. WASH-TRADING CHECK (Diversity)
        // Check how many times this specific buyer has rated this seller
        const pairQuery = await db.collection("transactions")
            .where("buyer_id", "==", buyer_id)
            .where("seller_id", "==", seller_id)
            .count()
            .get();

        const countBetweenPartners = pairQuery.data().count;
        const totalSellerTx = sellerData.total_transactions + 1; // +1 includes current

        // Calculate weight
        let weight = 1.0;
        const partnerRatio = countBetweenPartners / totalSellerTx;

        if (totalSellerTx > MIN_TX_THRESHOLD && partnerRatio > MAX_PARTNER_PERCENTAGE) {
            // Penalize if ratio is too high. 
            // e.g., if 50% from same partner -> weight drops significantly
            weight = Math.max(0.1, 1.0 - (partnerRatio - MAX_PARTNER_PERCENTAGE) * 2);
            console.log(`⚠️ Wash-Trading Suspicion for ${seller_id}. Partner Ratio: ${partnerRatio.toFixed(2)}. Weight reduced to: ${weight.toFixed(2)}`);
        }

        // 3. UPDATE SCORE (Exponential Moving Average)
        const alpha = 0.1; // Learning rate (10% influence of new rating)
        const ratingNormalized = rating * 20; // Scale 1-5 to 20-100
        
        // New Score = DecayedOld * (1-alpha) + NewRating * Weight * Alpha
        const newRep = (decayedRep * (1 - alpha)) + (ratingNormalized * weight * alpha);

        // 4. WRITE UPDATES
        await sellerRef.set({
            global_reputation: parseFloat(newRep.toFixed(2)),
            total_transactions: FieldValue.increment(1),
            last_updated: FieldValue.serverTimestamp()
        }, { merge: true });

        // Update transaction with the calculated weight for transparency
        await snapshot.ref.update({ reputation_weight: weight });

        console.log(`✅ Reputation updated for ${seller_id}: ${sellerData.global_reputation} -> ${newRep.toFixed(2)} (Decay: ${decayFactor.toFixed(4)})`);

    } catch (error) {
        console.error("Error updating reputation:", error);
    }
});
