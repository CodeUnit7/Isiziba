import { Negotiation } from "@/types/market";

export const formatAgentName = (id: string, agentNames: Record<string, string>): string => {
    if (agentNames[id]) return agentNames[id];
    if (!id) return "Unknown Agent";

    // If ID is ext-buyer-xxxx or ext-seller-xxxx and we don't have a name yet,
    // let's make it look nicer than just the ID.
    const parts = id.split('-');
    if (parts.length >= 2) {
        // e.g. ext-buyer-123 -> Buyer 123
        // Check if it matches the pattern ext-<type>-<uuid>
        if (parts[0] === 'ext' && parts.length >= 3) {
            const type = parts[1].charAt(0).toUpperCase() + parts[1].slice(1);
            const shortId = parts[parts.length - 1];
            return `${type} ${shortId}`;
        }
    }

    return id
        .replace('ext-', '')
        .replace('-reference', '')
        .replace('-agent', '')
        .split('-')
        .map(w => w.charAt(0).toUpperCase() + w.slice(1))
        .join(' ');
};

export const getAgentIdFromNegotiation = (neg: Negotiation, role: 'sender' | 'receiver'): string => {
    // In our backend model, the negotiation object has buyer_id and seller_id.
    // 'sender' and 'receiver' context depends on the specific message in history,
    // but at the negotiation level:
    if (role === 'sender') return neg.buyer_id || "unknown-buyer";
    return neg.seller_id || "unknown-seller";
};
