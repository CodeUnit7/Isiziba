'use client';

import { useEffect, useState, useRef, useLayoutEffect } from 'react';
import { WSMessage, FeedbackReport } from '@/types/market';
import { getApiUrl } from '@/lib/config';
import { useMarketContext } from '@/contexts/MarketContext';

type FeedbackItem = {
    type: string;
    negotiation_id: string;
    source: string;
    involved_agents?: string[];
    feedback?: {
        buyer_feedback: string;
        seller_feedback: string;
        strategy_score: number;
    };
    rating?: number;
    comment?: string;
    timestamp: number;
};

export default function FeedbackTerminal() {
    const [history, setHistory] = useState<FeedbackItem[]>([]);
    const { wsStatus, subscribe } = useMarketContext();

    const scrollRef = useRef<HTMLDivElement>(null);
    const lastScrollHeight = useRef<number>(0);

    // Scroll anchoring logic
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
    }, [history]);

    useEffect(() => {
        const fetchHistory = async () => {
            try {
                const res = await fetch(getApiUrl('/feedback/history'));
                if (res.ok) {
                    const data = await res.json();
                    setHistory(data.feedback || []);
                }
            } catch (err) {
                console.error("Failed to fetch feedback history:", err);
            }
        };

        fetchHistory();
    }, []);

    useEffect(() => {
        const unsubscribe = subscribe((msg: WSMessage) => {
            if (msg.type === 'feedback_report' || msg.type === 'user_feedback_received') {
                const newItem = msg.type === 'feedback_report'
                    ? { ...msg, source: 'Market Coach' }
                    : { ...msg.data, source: 'User', type: 'user_feedback' };

                setHistory((prev) => {
                    // Check if we already have feedback for this negotiation to update it instead of prepending
                    const index = prev.findIndex(h => h.negotiation_id === (newItem as any).negotiation_id && h.source === newItem.source);
                    if (index !== -1) {
                        const next = [...prev];
                        next[index] = { ...next[index], ...newItem };
                        return next;
                    }
                    return [newItem as FeedbackItem, ...prev].slice(0, 50);
                });
            }
        });
        return unsubscribe;
    }, [subscribe]);

    return (
        <div className="card" style={{ height: '600px', display: 'flex', flexDirection: 'column' }}>
            <div className="card-header" style={{ flexShrink: 0 }}>
                <span>Feedback Terminal</span>
                <span className="badge" style={{
                    backgroundColor: wsStatus === 'CONNECTED' ? '#10b981' : '#ef4444',
                    color: '#fff'
                }}>
                    {wsStatus === 'CONNECTED' ? 'LIVE' : 'OFFLINE'}
                </span>
            </div>
            <div
                ref={scrollRef}
                style={{
                    flex: 1,
                    overflowY: 'auto',
                    padding: '1rem',
                    scrollbarWidth: 'thin',
                    scrollbarColor: '#475569 #1e293b',
                    scrollBehavior: 'auto'
                }}
            >
                {history.length === 0 ? (
                    <div style={{ textAlign: 'center', color: 'var(--secondary)', marginTop: '2rem' }}>
                        Waiting for market feedback...
                    </div>
                ) : (
                    history.map((item) => {
                        const stableKey = `${item.negotiation_id}-${item.timestamp}-${item.source}`;
                        return (
                            <div key={stableKey} className="ticker-item" style={{
                                flexDirection: 'column',
                                alignItems: 'flex-start',
                                borderLeft: `4px solid ${item.source === 'User' ? '#3b82f6' : '#8b5cf6'}`,
                                paddingLeft: '0.75rem',
                                marginBottom: '1.5rem',
                                background: 'rgba(255,255,255,0.03)',
                                padding: '0.75rem',
                                borderRadius: '0 8px 8px 0',
                                position: 'relative',
                                overflow: 'hidden',
                                width: '100%'
                            }}>
                                <div style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    width: '100%',
                                    marginBottom: '0.25rem'
                                }}>
                                    <span style={{
                                        fontSize: '0.75rem',
                                        fontWeight: 700,
                                        color: item.source === 'User' ? '#3b82f6' : '#8b5cf6'
                                    }}>
                                        {item.source === 'User' ? 'USER SIGNAL' : 'MARKET COACH'}
                                    </span>
                                    <span style={{ fontSize: '0.7rem', color: 'var(--secondary)' }}>
                                        {new Date(item.timestamp * 1000).toLocaleTimeString()}
                                    </span>
                                </div>

                                <div style={{
                                    fontSize: '0.85rem',
                                    marginBottom: '0.4rem',
                                    color: '#fff',
                                    fontWeight: 500,
                                    width: '100%',
                                    wordBreak: 'break-word',
                                    overflowWrap: 'anywhere'
                                }}>
                                    {item.source === 'User' ? (
                                        <div style={{ width: '100%' }}>
                                            <div style={{ color: '#fcd34d', marginBottom: '4px', fontSize: '0.9rem' }}>
                                                {'★'.repeat(item.rating || 0)}{'☆'.repeat(5 - (item.rating || 0))}
                                            </div>
                                            {item.comment && (
                                                <div style={{
                                                    fontSize: '0.8rem',
                                                    fontStyle: 'italic',
                                                    color: '#cbd5e1',
                                                    marginTop: '0.25rem',
                                                    padding: '0.4rem',
                                                    backgroundColor: 'rgba(255,255,255,0.05)',
                                                    borderRadius: '4px',
                                                    width: '100%'
                                                }}>
                                                    "{item.comment}"
                                                </div>
                                            )}
                                        </div>
                                    ) : (
                                        <div style={{ width: '100%' }}>
                                            <div style={{
                                                fontSize: '0.75rem',
                                                color: '#a78bfa',
                                                marginBottom: '4px',
                                                fontWeight: 600,
                                                width: '100%'
                                            }}>
                                                Strategy Score: {item.feedback?.strategy_score}/10
                                            </div>
                                            <div style={{
                                                marginTop: '0.5rem',
                                                padding: '0.75rem',
                                                background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.1) 0%, rgba(59, 130, 246, 0.1) 100%)',
                                                border: '1px solid rgba(139, 92, 246, 0.3)',
                                                borderRadius: '8px',
                                                width: '100%',
                                                position: 'relative'
                                            }}>
                                                <div style={{ fontSize: '0.75rem', color: '#e2e8f0', marginBottom: '0.4rem' }}>
                                                    <strong style={{ color: '#60a5fa' }}>Buyer:</strong> {item.feedback?.buyer_feedback}
                                                </div>
                                                <div style={{ fontSize: '0.75rem', color: '#e2e8f0' }}>
                                                    <strong style={{ color: '#fb923c' }}>Seller:</strong> {item.feedback?.seller_feedback}
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                                <div style={{ fontSize: '0.65rem', color: 'var(--secondary)', marginTop: '0.5rem' }}>
                                    REF: {item.negotiation_id}
                                </div>
                            </div>
                        );
                    })
                )}
            </div>
            <style jsx>{`
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(-10px); }
                    to { opacity: 1; transform: translateY(0); }
                }
            `}</style>
        </div>
    );
}
