import * as admin from 'firebase-admin';

if (!admin.apps.length) {
    admin.initializeApp({
        projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || process.env.AGENT_MKT_PROJECT_ID
    });
}

const db = admin.firestore();

export { db };
