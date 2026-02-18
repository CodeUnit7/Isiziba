import { NextResponse } from 'next/server';
import { db } from '../../../lib/firebaseAdmin';

export const dynamic = 'force-dynamic';

export async function GET() {
    try {
        const snapshot = await db.collection('agents')
            .orderBy('global_reputation', 'desc')
            .get();

        const agents = snapshot.docs
            .map(doc => ({
                id: doc.id,
                ...doc.data()
            }))
            .filter((agent: any) => agent.id || agent.agent_id); // More inclusive

        return NextResponse.json(agents);
    } catch (error) {
        console.error('Error fetching agents:', error);
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
    }
}
