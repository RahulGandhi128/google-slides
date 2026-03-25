import React from 'react';
import { useSearchParams } from 'react-router-dom';
import ChatPage from './ChatPage';
import SheetsChatPage from './SheetsChatPage';

/**
 * Home route: renders slides chat or sheets chat based on ?agent=slides|sheets (default slides).
 */
export default function UnifiedHomePage() {
  const [searchParams] = useSearchParams();
  const agent = searchParams.get('agent') || 'slides';
  if (agent === 'sheets') {
    return <SheetsChatPage />;
  }
  return <ChatPage />;
}
