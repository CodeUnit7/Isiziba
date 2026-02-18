'use client';

import { useEffect, useState, useRef, useLayoutEffect } from 'react';
import { WSMessage, Transaction } from '@/types/market';
import { getApiUrl, CURRENCY } from '@/lib/config';
import { formatAgentName } from '@/lib/utils';

import { useMarketContext } from '@/contexts/MarketContext';

export default function LiveTicker() {
    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const { agentNames, refreshAgents, wsStatus, subscribe } = useMarketContext();

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
    }, [transactions]);

    // Initial fetch of recent transactions and agent names
    useEffect(() => {
        const fetchInitialData = async () => {
            try {
                const txRes = await fetch(getApiUrl('/market/trends'));
                const txData = await txRes.json();

                if (txData.trends) {
                    const initialTx = txData.trends.map((t: any) => ({
                        id: t.tx_id || Math.random().toString(),
                        buyer_id: t.buyer_id || 'unknown',
                        seller_id: t.seller_id || 'unknown',
                        price: t.price,
                        amount: t.price, // Backward compat
                        product: t.product,
                        timestamp: t.timestamp
                    })).reverse();
                    setTransactions(initialTx);
                }
            } catch (err) {
                console.error("Failed to fetch initial ticker data:", err);
            }
        };

        fetchInitialData();
        refreshAgents(); // Ensure we have latest names
    }, []);

    // WebSocket listener for real-time updates
    useEffect(() => {
        const unsubscribe = subscribe((msg: WSMessage) => {
            if (msg.type === 'market_event') {
                const data = msg.data;
                // Check if it's a completed transaction
                if (data.buyer_id && data.seller_id && (data.amount !== undefined || data.price !== undefined) && data.status === 'COMPLETED') {
                    setTransactions(prev => {
                        if (prev.find(t => t.id === (data.tx_id || data.id))) return prev;
                        const newTx: Transaction = {
                            id: data.tx_id || data.id,
                            buyer_id: data.buyer_id,
                            seller_id: data.seller_id,
                            price: data.price || data.amount,
                            amount: data.amount || data.price,
                            product: data.product,
                            timestamp: data.timestamp
                        };
                        return [newTx, ...prev].slice(0, 50);
                    });
                }
            }
        });
        return unsubscribe;
    }, [subscribe]);

    return (
        <div className="card" style={{ height: '600px', display: 'flex', flexDirection: 'column' }}>
            <div className="card-header" style={{ flexShrink: 0 }}>
                <span>Live Transactions</span>
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
                {transactions.length === 0 ? (
                    <div style={{ color: 'var(--secondary)', textAlign: 'center' }}>
                        Waiting for transactions...
                    </div>
                ) : (
                    transactions.map((tx) => {
                        const stableKey = `${tx.id}-${tx.timestamp}`;
                        return (
                            <div key={stableKey} className="ticker-item" style={{
                                flexDirection: 'column',
                                alignItems: 'flex-start',
                                borderLeft: '4px solid #10b981',
                                paddingLeft: '0.75rem',
                                marginBottom: '1.5rem',
                                background: 'rgba(255,255,255,0.03)',
                                padding: '0.75rem',
                                borderRadius: '0 8px 8px 0',
                                position: 'relative'
                            }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', marginBottom: '0.25rem' }}>
                                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#10b981' }}>
                                        CONFIRMED
                                    </span>
                                    <span style={{ fontSize: '0.7rem', color: 'var(--secondary)' }}>
                                        {new Date(tx.timestamp * 1000).toLocaleTimeString()}
                                    </span>
                                </div>
                                <div style={{ fontSize: '0.85rem', marginBottom: '0.25rem', color: '#fff', fontWeight: 500 }}>
                                    <div style={{ fontSize: '0.75rem', color: '#10b981', marginBottom: '2px', fontWeight: 600 }}>
                                        {tx.product || "Transaction"}
                                    </div>
                                    <div style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                                        <span style={{ color: 'var(--secondary)', fontWeight: 600, letterSpacing: '0.02em' }}>
                                            Buyer→Seller
                                        </span>
                                        <span style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
                                        <span className="font-mono text-xs text-slate-400">
                                            {formatAgentName(tx.seller_id, agentNames)} &rarr; {formatAgentName(tx.buyer_id, agentNames)}
                                        </span>
                                    </div>
                                </div>
                                <div className="price" style={{ color: '#10b981', fontSize: '0.9rem', fontWeight: 600 }}>
                                    {(tx.price || tx.amount) ? `${Number(tx.price || tx.amount).toFixed(2)} ${CURRENCY}` : 'N/A'}
                                </div>
                                <div style={{ fontSize: '0.65rem', color: 'var(--secondary)', marginTop: '0.5rem' }}>
                                    ID: {tx.id.slice(0, 12)}...
                                </div>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
}
