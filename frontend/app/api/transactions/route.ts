import { NextResponse } from 'next/server';
import { db } from '../../../lib/firebaseAdmin';

export const dynamic = 'force-dynamic';

export async function GET() {
    try {
        const snapshot = await db.collection('transactions')
            .orderBy('timestamp', 'desc')
            .limit(20)
            .get();

        const transactions = snapshot.docs.map(doc => ({
            id: doc.id,
            ...doc.data()
        }));

        return NextResponse.json(transactions);
    } catch (error) {
        console.error('Error fetching transactions:', error);
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
    }
}
