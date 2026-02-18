import LiveTicker from '../components/LiveTicker';
import ReputationLeaderboard from '../components/ReputationLeaderboard';
import OrderBook from '../components/OrderBook';
import StatusMonitor from '../components/StatusMonitor';
import NegotiationFeed from '../components/NegotiationFeed';
import FeedbackTerminal from '../components/FeedbackTerminal';
import PriceTrendChart from '../components/PriceTrendChart';

export default function Home() {
    return (
        <main className="grid" style={{
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: '1.5rem',
            padding: '1.5rem'
        }}>
            <LiveTicker />
            <FeedbackTerminal />
            <NegotiationFeed />
            <StatusMonitor />
            <div style={{ gridColumn: 'span 2' }}>
                <ReputationLeaderboard />
            </div>
            <div style={{ gridColumn: 'span 2' }}>
                <OrderBook />
            </div>
            <div style={{ gridColumn: 'span 4' }}>
                <PriceTrendChart />
            </div>
        </main>
    );
}
