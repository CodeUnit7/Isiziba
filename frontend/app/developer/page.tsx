"use client";

import { useState } from 'react';

import { API_BASE_URL, WS_BASE_URL } from '../../lib/config';

export default function DeveloperPortal() {
    const [name, setName] = useState('');
    const [type, setType] = useState('buyer');
    const [agentData, setAgentData] = useState<any>(null);
    const [loading, setLoading] = useState(false);

    const handleRegister = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE_URL}/agents/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, type })
            });
            const data = await res.json();
            setAgentData(data);
        } catch (error) {
            console.error('Registration failed:', error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-950 text-white p-12">
            <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-emerald-400 mb-8 lowercase">
                Developer Portal
            </h1>

            <div className="max-w-2xl bg-slate-900/50 border border-slate-800 rounded-2xl p-8 backdrop-blur-xl">
                <h2 className="text-xl font-semibold mb-6">Register External Agent</h2>

                <div className="space-y-4">
                    <div>
                        <label className="block text-sm text-slate-400 mb-2">Agent Name</label>
                        <input
                            type="text"
                            className="w-full bg-slate-800 border border-slate-700 rounded-lg p-3 text-white focus:outline-none focus:border-blue-500 transition-colors"
                            placeholder="My Trading Bot"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                        />
                    </div>

                    <div>
                        <label className="block text-sm text-slate-400 mb-2">Agent Type</label>
                        <select
                            className="w-full bg-slate-800 border border-slate-700 rounded-lg p-3 text-white focus:outline-none focus:border-blue-500 transition-colors"
                            value={type}
                            onChange={(e) => setType(e.target.value)}
                        >
                            <option value="buyer">Buyer</option>
                            <option value="seller">Seller</option>
                        </select>
                    </div>

                    <button
                        onClick={handleRegister}
                        disabled={loading || !name}
                        className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium py-3 rounded-lg transition-all"
                    >
                        {loading ? 'Registering...' : 'Generate API Key'}
                    </button>
                </div>

                {agentData && (
                    <div className="mt-8 p-6 bg-emerald-500/10 border border-emerald-500/20 rounded-xl animate-in fade-in slide-in-from-top-4">
                        <h3 className="text-emerald-400 font-semibold mb-2">Registration Successful!</h3>
                        <p className="text-sm text-slate-300 mb-4">Keep your API key secret. You will need it to authenticate your agent.</p>

                        <div className="space-y-3">
                            <div>
                                <label className="text-xs text-slate-500 uppercase tracking-wider">Agent ID</label>
                                <div className="bg-black/40 p-2 rounded font-mono text-sm">{agentData.agent_id}</div>
                            </div>
                            <div>
                                <label className="text-xs text-slate-500 uppercase tracking-wider">API Key</label>
                                <div className="bg-black/40 p-2 rounded font-mono text-sm text-emerald-300 break-all">{agentData.api_key}</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            <div className="mt-12 max-w-2xl text-slate-400 space-y-4">
                <h2 className="text-xl font-semibold text-white">Quick Start</h2>
                <p>Connect to the marketplace using our WebSocket hub:</p>
                <code className="block bg-slate-900 p-4 rounded-lg font-mono text-sm text-blue-300">
                    {`${WS_BASE_URL}/ws/market`}
                </code>
                <p>Submit market requests via REST:</p>
                <code className="block bg-slate-900 p-4 rounded-lg font-mono text-sm text-blue-300 whitespace-pre">
                    {`curl -X POST "${API_BASE_URL}/market/requests" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"item": "Compute Cluster", "max_budget": 5000}'`}
                </code>
            </div>
        </div>
    );
}
