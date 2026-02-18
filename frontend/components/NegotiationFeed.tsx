'use client';

import { useEffect, useState, useRef, useLayoutEffect } from 'react';
import { WSMessage, Negotiation } from '@/types/market';
import { getApiUrl, CURRENCY } from '@/lib/config';
import { formatAgentName, getAgentIdFromNegotiation } from '@/lib/utils';
import { useMarketContext } from '@/contexts/MarketContext';

export default function NegotiationFeed() {
    const [negotiations, setNegotiations] = useState<Negotiation[]>([]);
    const [feedbackMap, setFeedbackMap] = useState<Record<string, any>>({});
    const scrollRef = useRef<HTMLDivElement>(null);
    const lastScrollHeight = useRef<number>(0);

    // Use shared context
    const { agentNames, agentRoles, wsStatus, subscribe } = useMarketContext();

    // Scroll anchoring logic (Matched with FeedbackTerminal)
    useLayoutEffect(() => {
        const container = scrollRef.current;
        if (!container) return;

        const isAtTop = container.scrollTop <= 10;

        if (isAtTop) {
            container.scrollTop = 0;
        } else {
            const heightDiff = container.scrollHeight - lastScrollHeight.current;
            if (heightDiff > 0) {
                container.scrollTop += heightDiff;
            }
        }
        lastScrollHeight.current = container.scrollHeight;
    }, [negotiations]);

    // Initial fetch
    useEffect(() => {
        const fetchData = async () => {
            try {
                const negRes = await fetch(getApiUrl('/market/negotiations'));
                if (negRes.ok) {
                    const data = await negRes.json();
                    setNegotiations(data.negotiations || []);
                }
            } catch (err) {
                console.error('Failed to fetch negotiation data:', err);
            }
        };
        fetchData();
    }, []);

    // Subscribe to shared WS events
    useEffect(() => {
        return subscribe((msg: WSMessage) => {
            if (msg.type === 'market_event' && msg.data.type === 'Proposal') {
                const newNeg = msg.data as Negotiation;
                setNegotiations((prev) => {
                    const index = prev.findIndex(n => n.negotiation_id === newNeg.negotiation_id);
                    if (index !== -1) {
                        const next = [...prev];
                        next[index] = { ...next[index], ...newNeg };
                        return next;
                    }
                    // Keep list bounded to 100 for memory safety
                    return [newNeg, ...prev].slice(0, 100);
                });
            } else if (msg.type === 'feedback_report') {
                if (msg.negotiation_id) {
                    setFeedbackMap((prev) => ({
                        ...prev,
                        [msg.negotiation_id!]: msg.feedback
                    }));
                }
            }
        });
    }, [subscribe]);

    const getRoleColorClass = (agentId: string) => {
        const role = agentRoles[agentId];
        if (role === 'buyer') return 'blue';
        if (role === 'seller') return 'amber';

        if (agentId.toLowerCase().includes('buyer')) return 'blue';
        if (agentId.toLowerCase().includes('seller')) return 'amber';
        return 'slate';
    };

    return (
        <div className="card" style={{ height: '600px', display: 'flex', flexDirection: 'column' }}>
            <div className="card-header" style={{ flexShrink: 0 }}>
                <span>Live Negotiations ({negotiations.length})</span>
                <span className="badge" style={{
                    backgroundColor: wsStatus === 'CONNECTED' ? '#10b981' : '#ef4444',
                    color: '#fff'
                }}>
                    {wsStatus === 'CONNECTED' ? 'LIVE' : 'OFFLINE'}
                </span>
            </div>

            <div ref={scrollRef} style={{
                flex: 1,
                overflowY: 'auto',
                padding: '1rem',
                scrollbarWidth: 'thin',
                scrollbarColor: '#475569 #1e293b'
            }}>
                {negotiations.length === 0 ? (
                    <div style={{ textAlign: 'center', color: 'var(--secondary)', marginTop: '2rem' }}>
                        Waiting for market activity...
                    </div>
                ) : (
                    negotiations.map((neg) => {
                        const action = neg.action || neg.status || "PROPOSAL";
                        const price = neg.price || neg.last_price;
                        const feedback = neg.negotiation_id ? feedbackMap[neg.negotiation_id] : null;

                        const senderId = neg.sender_id || neg.buyer_id || getAgentIdFromNegotiation(neg, 'sender');
                        const receiverId = neg.receiver_id || neg.seller_id || getAgentIdFromNegotiation(neg, 'receiver');

                        const roleColor = getRoleColorClass(senderId) === 'blue' ? '#3b82f6' : '#f59e0b';
                        const stableKey = `${neg.negotiation_id}-${neg.timestamp}-${neg.offer_id || ''}`;

                        return (
                            <div
                                key={stableKey}
                                className="ticker-item"
                                style={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'flex-start',
                                    borderLeft: `4px solid ${roleColor}`,
                                    paddingLeft: '0.75rem',
                                    background: 'rgba(255,255,255,0.03)',
                                    padding: '0.75rem',
                                    borderRadius: '0 8px 8px 0',
                                    transition: 'background 0.2s ease',
                                    marginBottom: '1.5rem',
                                    position: 'relative'
                                }}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', marginBottom: '0.25rem' }}>
                                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: roleColor, textTransform: 'uppercase' }}>
                                        {action}
                                    </span>
                                    <span style={{ fontSize: '0.7rem', color: 'var(--secondary)' }}>
                                        {neg.timestamp ? new Date(neg.timestamp * 1000).toLocaleTimeString() : 'Just now'}
                                    </span>
                                </div>

                                <div style={{ fontSize: '0.85rem', marginBottom: '0.25rem', color: '#fff', fontWeight: 500, width: '100%' }}>
                                    <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#fff', marginBottom: '2px' }}>
                                        {neg.product || "Negotiation"}
                                    </div>
                                    <div style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                                        <span style={{ color: 'var(--secondary)', fontWeight: 600 }}>
                                            {formatAgentName(senderId, agentNames)} &rarr; {formatAgentName(receiverId, agentNames)}
                                        </span>
                                    </div>
                                </div>

                                {price && (
                                    <div style={{ color: roleColor, fontSize: '0.9rem', fontWeight: 700, marginTop: '0.25rem' }}>
                                        {Number(price).toFixed(2)} {CURRENCY}
                                    </div>
                                )}

                                {(neg.reasoning || neg.reason) && (
                                    <div style={{
                                        fontSize: '0.75rem',
                                        fontStyle: 'italic',
                                        color: '#cbd5e1',
                                        marginTop: '0.5rem',
                                        padding: '0.5rem',
                                        backgroundColor: 'rgba(255,255,255,0.05)',
                                        borderRadius: '4px',
                                        width: '100%',
                                        borderLeft: '2px solid rgba(255,255,255,0.1)',
                                        overflowWrap: 'anywhere'
                                    }}>
                                        "{neg.reasoning || neg.reason}"
                                    </div>
                                )}

                                {feedback && (
                                    <div style={{
                                        position: 'absolute',
                                        right: '0.75rem',
                                        bottom: '0.75rem',
                                        fontSize: '0.65rem',
                                        background: '#8b5cf6',
                                        color: '#fff',
                                        padding: '2px 6px',
                                        borderRadius: '4px',
                                        fontWeight: 700
                                    }}>
                                        Score: {feedback.strategy_score}
                                    </div>
                                )}
                            </div>
                        );
                    })
                )}
            </div>
            <style jsx>{`
                .ticker-item:hover {
                    background: rgba(255,255,255,0.06) !important;
                }
            `}</style>
        </div>
    );
}
function StarRating({ negotiationId, onRate }: { negotiationId: string, onRate: (rating: number) => void }) {
    const [rating, setRating] = useState(0);
    const [hover, setHover] = useState(0);
    const [submitted, setSubmitted] = useState(false);

    if (submitted) {
        return (
            <div className="text-xs text-emerald-500 italic">
                ✓ Feedback submitted. Thank you!
            </div>
        );
    }

    return (
        <div className="flex gap-1 items-center">
            {[1, 2, 3, 4, 5].map((star) => (
                <button
                    key={star}
                    onClick={async () => {
                        setRating(star);
                        setSubmitted(true);
                        onRate(star);
                    }}
                    onMouseEnter={() => setHover(star)}
                    onMouseLeave={() => setHover(0)}
                    className={`bg-none border-none cursor-pointer p-0 text-xl transition-colors duration-100 outline-none ${(hover || rating) >= star ? 'text-amber-300' : 'text-slate-600'}`}
                >
                    ★
                </button>
            ))}
        </div>
    );
}
