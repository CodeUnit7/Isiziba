export interface WSMessage {
    type: string;
    data?: any;
    negotiation_id?: string;
    feedback?: any;
    involved_agents?: string[];
    agent_id?: string;
    name?: string;
    status?: string;
    activity?: string;
    timestamp?: number;
}

export interface FeedbackReport {
    negotiation_id: string;
    feedback: {
        buyer_feedback: string;
        seller_feedback: string;
        strategy_score: number;
    };
    involved_agents: string[];
}

export interface MarketEvent {
    type: string;
    data: any;
}

export interface Agent {
    id: string;
    agent_id?: string; // Some endpoints return this
    name: string;
    type: 'buyer' | 'seller';
    api_key?: string;
    global_reputation?: number; // Backend field
    reputation?: number; // Alias
    total_transactions?: number;
    transactions?: number; // Alias
    status?: string; // Runtime status in frontend
    activity?: string; // Latest activity description
    timestamp?: number; // Last update timestamp
}

export interface Transaction {
    id: string;
    buyer_id: string;
    seller_id: string;
    product: string;
    price: number;
    amount?: number; // Alias for price in some components
    timestamp: number;
}

export interface Negotiation {
    negotiation_id: string; // Backend sends negotiation_id
    id?: string; // Some components might use id alias
    offer_id?: string;
    product: string;
    price: number;
    step?: number;
    max_steps?: number;
    buyer_id?: string;
    seller_id?: string;
    sender_id?: string; // In history items or events
    receiver_id?: string;
    status: 'ACTIVE' | 'COMPLETED' | 'FAILED' | 'OPEN';
    action?: 'OFFER' | 'COUNTER' | 'ACCEPT' | 'REJECT' | 'PROPOSAL';
    history?: NegotiationHistoryItem[];
    timestamp?: number;
    last_price?: number;
    reasoning?: string;
    reason?: string;
}

export interface NegotiationHistoryItem {
    sender_id: string;
    action: 'OFFER' | 'COUNTER' | 'ACCEPT' | 'REJECT';
    price: number;
    reasoning?: string;
    timestamp: number;
}

export interface MarketTrend {
    tx_id: string;
    buyer_id: string;
    seller_id: string;
    product: string;
    price: number;
    timestamp: number;
}

export interface MarketData {
    trends: MarketTrend[];
    active_negotiations: number;
    volume_24h: number;
}

export interface Offer {
    id: string;
    offer_id?: string;
    price: number;
    amount?: number;
    product: string;
    agent_id: string;
    agent_name?: string;
    sender_id?: string;
    seller_id?: string;
    timestamp: number;
    type: 'ask' | 'bid';
}

export interface AgentStatus {
    id: string;
    agent_id?: string;
    name: string;
    type: 'buyer' | 'seller' | string;
    status: string;
    activity: string;
    timestamp: number;
    reputation: number;
    global_reputation?: number;
    total_transactions?: number;
}
