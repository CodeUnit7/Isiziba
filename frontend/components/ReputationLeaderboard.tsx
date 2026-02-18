'use client';

import { useEffect, useState } from 'react';
import { Agent, WSMessage } from '@/types/market';
import { getApiUrl } from '@/lib/config';
import { useMarketContext } from '@/contexts/MarketContext';

const formatAgentName = (agent: Agent) => {
    if (agent.name) return agent.name;
    const id = agent.agent_id || agent.id || "";
    return id
        .replace('-reference', '')
        .replace('-agent', '')
        .split('-')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
};

export default function ReputationLeaderboard() {
    const [agents, setAgents] = useState<Agent[]>([]);
    const { wsStatus, subscribe } = useMarketContext();

    // Initial fetch of agents
    useEffect(() => {
        const fetchAgents = async () => {
            try {
                const res = await fetch(getApiUrl('/agents'));
                const data = await res.json();
                if (Array.isArray(data)) {
                    setAgents(data);
                }
            } catch (err) {
                console.error("Leaderboard fetch error:", err);
            }
        };

        fetchAgents();
    }, []);

    // WebSocket listener for real-time score updates
    useEffect(() => {
        const unsubscribe = subscribe((msg: WSMessage) => {
            if (msg.type === 'market_event') {
                const data = msg.data;
                // If a transaction is completed, increment scores locally
                if (data.status === 'COMPLETED' && data.buyer_id && data.seller_id) {
                    setAgents(prev => {
                        const next = [...prev];
                        let changed = false;

                        // Update buyer
                        const buyerIdx = next.findIndex(a => a.id === data.buyer_id);
                        if (buyerIdx !== -1) {
                            next[buyerIdx] = {
                                ...next[buyerIdx],
                                global_reputation: (next[buyerIdx].global_reputation || 0) + 1,
                                total_transactions: (next[buyerIdx].total_transactions || 0) + 1
                            };
                            changed = true;
                        }

                        // Update seller
                        const sellerIdx = next.findIndex(a => a.id === data.seller_id);
                        if (sellerIdx !== -1) {
                            next[sellerIdx] = {
                                ...next[sellerIdx],
                                global_reputation: (next[sellerIdx].global_reputation || 0) + 1,
                                total_transactions: (next[sellerIdx].total_transactions || 0) + 1
                            };
                            changed = true;
                        }

                        return changed ? next.sort((a, b) => (b.global_reputation || 0) - (a.global_reputation || 0)) : prev;
                    });
                }
            }
        });
        return unsubscribe;
    }, [subscribe]);

    return (
        <div className="card" style={{ height: '600px', display: 'flex', flexDirection: 'column', padding: 0 }}>
            <div className="card-header" style={{ flexShrink: 0, padding: '1rem 1.5rem', marginBottom: 0, borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <span>Reputation Leaderboard</span>
                <span className="badge" style={{
                    backgroundColor: wsStatus === 'CONNECTED' ? '#10b981' : '#ef4444',
                    color: '#fff'
                }}>
                    {wsStatus === 'CONNECTED' ? 'LIVE' : 'OFFLINE'}
                </span>
            </div>

            {/* Fixed Table Header */}
            <div style={{
                display: 'flex',
                padding: '0.75rem 1.5rem',
                fontSize: '0.7rem',
                color: '#64748b',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                fontWeight: 700,
                borderBottom: '1px solid rgba(255,255,255,0.03)',
                background: 'rgba(255,255,255,0.01)'
            }}>
                <div style={{ flex: 4 }}>Agent</div>
                <div style={{ flex: 4 }}>Reputation</div>
                <div style={{ flex: 2, textAlign: 'right' }}>Deals</div>
            </div>

            <div style={{
                flex: 1,
                overflowY: 'auto',
                padding: '1rem 1.5rem',
                scrollbarWidth: 'thin',
                scrollbarColor: '#475569 #1e293b'
            }} className="custom-scrollbar">
                {agents.length === 0 ? (
                    <div style={{ textAlign: 'center', color: 'var(--secondary)', marginTop: '2rem' }}>
                        Loading agents...
                    </div>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        {agents.map((agent) => (
                            <div key={agent.id} className="leaderboard-item" style={{
                                display: 'flex',
                                alignItems: 'center',
                                background: 'rgba(255,255,255,0.03)',
                                borderRadius: '8px',
                                padding: '1rem',
                                borderLeft: `4px solid ${(agent.agent_id || agent.id || "").toLowerCase().includes('buyer') ? '#3b82f6' : '#f59e0b'}`,
                                transition: 'background 0.2s ease, transform 0.2s ease'
                            }}>
                                {/* Agent Info */}
                                <div style={{ flex: 4 }}>
                                    <div style={{ fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                                        <span style={{ color: (agent.agent_id || agent.id || "").toLowerCase().includes('buyer') ? '#3b82f6' : '#f59e0b', fontWeight: 600 }}>
                                            {(agent.agent_id || agent.id || "").toLowerCase().includes('buyer') ? 'Buyer' : 'Seller'}
                                        </span>
                                    </div>
                                    <div style={{ fontWeight: 600, color: '#fff', fontSize: '0.9rem' }}>{formatAgentName(agent)}</div>
                                    <div style={{ fontSize: '0.65rem', color: '#64748b', fontFamily: 'monospace' }}>
                                        {(agent.agent_id || agent.id || "").split('-').pop()}
                                    </div>
                                </div>

                                {/* Reputation Bar */}
                                <div style={{ flex: 4, paddingRight: '1.5rem' }}>
                                    <div style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '0.75rem'
                                    }}>
                                        <div style={{
                                            flex: 1,
                                            height: '4px',
                                            background: '#334155',
                                            borderRadius: '2px',
                                            overflow: 'hidden'
                                        }}>
                                            <div style={{
                                                width: `${Math.min(((agent.global_reputation || 0) / Math.max(...agents.map(a => a.global_reputation || 0), 100)) * 100, 100)}%`,
                                                height: '100%',
                                                background: (agent.global_reputation || 0) > 80 ? '#10b981' :
                                                    (agent.global_reputation || 0) > 50 ? '#3b82f6' : '#ef4444',
                                                borderRadius: '2px',
                                                transition: 'width 1s cubic-bezier(0.4, 0, 0.2, 1)'
                                            }} />
                                        </div>
                                        <div style={{ fontSize: '0.8rem', minWidth: '2.5rem', textAlign: 'right', fontWeight: 700, color: '#fff' }}>
                                            {Number(agent.global_reputation || 0).toFixed(1)}
                                        </div>
                                    </div>
                                </div>

                                {/* Transactions */}
                                <div style={{ flex: 2, textAlign: 'right', fontFamily: 'monospace', fontWeight: 700, color: '#f59e0b', fontSize: '1.1rem' }}>
                                    {agent.total_transactions || 0}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
            <style jsx>{`
                .leaderboard-item:hover {
                    background: rgba(255,255,255,0.06) !important;
                    transform: translateX(4px);
                }
            `}</style>
        </div>
    );
}
