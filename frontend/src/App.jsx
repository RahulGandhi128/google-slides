import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import DrivePage from './pages/DrivePage';
import ChatPage from './pages/ChatPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DrivePage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
